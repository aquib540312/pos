import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import require_permission
from app.core.exceptions import ConflictError, DomainError, NotFoundError, ValidationError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.models.sync import SyncTerminal
from app.modules.sync.deps import get_current_terminal
from app.modules.sync.schemas import (
    ChangeLogEntryResponse,
    ConflictResolveRequest,
    ConflictResponse,
    PullResponse,
    PushRequest,
    PushResponse,
    SyncStatusResponse,
    TerminalRegisterRequest,
    TerminalRegisterResponse,
    TerminalStatusResponse,
)
from app.modules.sync.service import SyncService

router = APIRouter(prefix="/api/v1/sync", tags=["sync"])

_ERROR_STATUS = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ConflictError: status.HTTP_409_CONFLICT,
}


def _handle(exc: DomainError, db: Session):
    db.rollback()
    for exc_type, code in _ERROR_STATUS.items():
        if isinstance(exc, exc_type):
            raise HTTPException(code, str(exc)) from exc
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/register", response_model=TerminalRegisterResponse, status_code=status.HTTP_201_CREATED)
def register_terminal(
    payload: TerminalRegisterRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SYNC_MANAGE)),
):
    """Called once when setting up a new terminal (or re-run safely any
    time -- same device_fingerprint returns the same terminal rather than
    creating a duplicate). Requires a real logged-in manager/admin; the
    api_key it returns is what the unattended background worker uses for
    every subsequent push/pull."""
    terminal = SyncService(db).register_terminal(
        user.organization_id, payload.branch_id, payload.name, payload.device_fingerprint
    )
    db.commit()
    return terminal


@router.post("/push", response_model=PushResponse)
def push(
    payload: PushRequest,
    db: Session = Depends(get_db),
    terminal: SyncTerminal = Depends(get_current_terminal),
):
    settings = get_settings()
    if len(payload.offline_sales) > settings.sync_push_max_batch_size:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Batch of {len(payload.offline_sales)} exceeds max {settings.sync_push_max_batch_size} -- split it up",
        )
    results = SyncService(db).push_offline_sales(terminal, payload.offline_sales)
    return PushResponse(results=results)


@router.get("/pull", response_model=PullResponse)
def pull(
    cursor: int = 0,
    entity_types: str | None = None,
    db: Session = Depends(get_db),
    terminal: SyncTerminal = Depends(get_current_terminal),
):
    """`entity_types` is an optional comma-separated filter (e.g.
    `product,customer`) so a terminal can do a partial sync -- catch up on
    products first and defer a large inventory backlog to a quieter
    moment, for instance -- instead of always pulling every entity type
    together."""
    settings = get_settings()
    types = [t.strip() for t in entity_types.split(",") if t.strip()] if entity_types else None
    rows, next_cursor, has_more = SyncService(db).pull(
        terminal.organization_id, cursor, types, settings.sync_pull_page_size
    )
    changes = [
        ChangeLogEntryResponse(
            id=row.id, entity_type=row.entity_type, entity_id=row.entity_id, operation=row.operation,
            payload=json.loads(row.payload_json), created_at=row.created_at,
        )
        for row in rows
    ]
    return PullResponse(changes=changes, next_cursor=next_cursor, has_more=has_more)


@router.get("/conflicts", response_model=list[ConflictResponse])
def list_conflicts(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SYNC_MANAGE)),
):
    conflicts = SyncService(db).list_conflicts(user.organization_id, status_filter)
    return [
        ConflictResponse(
            id=c.id, terminal_id=c.terminal_id, offline_sale_id=c.offline_sale_id, conflict_type=c.conflict_type,
            details=json.loads(c.details_json), status=c.status, resolution=c.resolution,
            resolution_notes=c.resolution_notes, created_at=c.created_at, resolved_at=c.resolved_at,
        )
        for c in conflicts
    ]


@router.post("/conflicts/{conflict_id}/resolve", response_model=ConflictResponse)
def resolve_conflict(
    conflict_id: uuid.UUID,
    payload: ConflictResolveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SYNC_MANAGE)),
):
    service = SyncService(db)
    try:
        conflict = service.resolve_conflict(user.organization_id, conflict_id, payload.resolution, payload.notes, user.id)
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return ConflictResponse(
        id=conflict.id, terminal_id=conflict.terminal_id, offline_sale_id=conflict.offline_sale_id,
        conflict_type=conflict.conflict_type, details=json.loads(conflict.details_json), status=conflict.status,
        resolution=conflict.resolution, resolution_notes=conflict.resolution_notes, created_at=conflict.created_at,
        resolved_at=conflict.resolved_at,
    )


@router.get("/status", response_model=SyncStatusResponse)
def sync_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SYNC_MANAGE)),
):
    terminals, open_conflicts, latest_change_log_id = SyncService(db).status(user.organization_id)
    return SyncStatusResponse(
        terminals=[TerminalStatusResponse.model_validate(t) for t in terminals],
        open_conflicts=open_conflicts,
        latest_change_log_id=latest_change_log_id,
    )
