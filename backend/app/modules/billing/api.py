import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import ConflictError, NotFoundError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.billing.schemas import ShiftCloseRequest, ShiftOpenRequest, ShiftResponse, ShiftSummaryResponse
from app.modules.billing.service import ShiftService

router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


@router.get("/shifts/current", response_model=ShiftSummaryResponse | None)
def get_current_shift(
    branch_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SHIFT_MANAGE)),
):
    current = ShiftService(db).current_shift(user.id, branch_id)
    if current is None:
        return None
    shift, running_cash_sales = current
    return ShiftSummaryResponse(
        id=shift.id,
        branch_id=shift.branch_id,
        user_id=shift.user_id,
        opened_at=shift.opened_at,
        closed_at=shift.closed_at,
        opening_cash=shift.opening_cash,
        expected_closing_cash=shift.expected_closing_cash,
        counted_closing_cash=shift.counted_closing_cash,
        cash_variance=shift.cash_variance,
        status=shift.status,
        running_cash_sales=running_cash_sales,
    )


@router.get("/shifts", response_model=list[ShiftResponse])
def list_shifts(
    branch_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SHIFT_MANAGE)),
):
    return ShiftService(db).shifts.list(user.organization_id, branch_id, limit)


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
