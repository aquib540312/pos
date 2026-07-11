import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import ConflictError, NotFoundError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.billing.schemas import ShiftCloseRequest, ShiftOpenRequest, ShiftResponse
from app.modules.billing.service import ShiftService

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.post("/shifts/open", response_model=ShiftResponse, status_code=status.HTTP_201_CREATED)
def open_shift(
    payload: ShiftOpenRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SHIFT_MANAGE)),
):
    try:
        shift = ShiftService(db).open_shift(user.organization_id, payload.branch_id, user.id, payload.opening_cash)
        db.commit()
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return shift


@router.post("/shifts/{shift_id}/close", response_model=ShiftResponse)
def close_shift(
    shift_id: uuid.UUID,
    payload: ShiftCloseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SHIFT_MANAGE)),
):
    try:
        shift = ShiftService(db).close_shift(shift_id, payload.counted_closing_cash)
        db.commit()
    except (ConflictError, NotFoundError) as exc:
        db.rollback()
        status_code = status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_409_CONFLICT
        raise HTTPException(status_code, str(exc)) from exc
    return shift
