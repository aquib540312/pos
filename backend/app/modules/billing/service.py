import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.billing import Shift
from app.modules.billing.repository import ShiftRepository


class ShiftService:
    def __init__(self, db: Session):
        self.db = db
        self.shifts = ShiftRepository(db)

    def open_shift(self, organization_id: uuid.UUID, branch_id: uuid.UUID, user_id: uuid.UUID, opening_cash: float) -> Shift:
        if self.shifts.get_open_shift(user_id, branch_id) is not None:
            raise ConflictError("You already have an open shift at this branch")
        shift = Shift(
            organization_id=organization_id,
            branch_id=branch_id,
            user_id=user_id,
            opened_at=datetime.now(timezone.utc),
            opening_cash=opening_cash,
            status="open",
        )
        return self.shifts.add(shift)

    def current_shift(self, user_id: uuid.UUID, branch_id: uuid.UUID) -> tuple[Shift, float] | None:
        """The cashier's own open shift at this branch, plus cash sales
        rung up on it so far -- lets the shift screen show a running
        total before the cashier actually closes out, without exposing
        sum_cash_payments as its own endpoint."""
        shift = self.shifts.get_open_shift(user_id, branch_id)
        if shift is None:
            return None
        return shift, self.shifts.sum_cash_payments(shift.id)

    def close_shift(self, shift_id: uuid.UUID, counted_closing_cash: float) -> Shift:
        shift = self.shifts.get(shift_id)
        if shift is None:
            raise NotFoundError(f"Shift {shift_id} not found")
        if shift.status != "open":
            raise ConflictError("Shift is already closed")
        cash_sales = self.shifts.sum_cash_payments(shift_id)
        expected = float(shift.opening_cash) + cash_sales
        shift.expected_closing_cash = expected
        shift.counted_closing_cash = counted_closing_cash
        shift.cash_variance = counted_closing_cash - expected
        shift.closed_at = datetime.now(timezone.utc)
        shift.status = "closed"
        self.db.flush()
        return shift
