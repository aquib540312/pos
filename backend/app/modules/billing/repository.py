import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.billing import Payment, Shift


class ShiftRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, shift_id: uuid.UUID) -> Shift | None:
        return self.db.get(Shift, shift_id)

    def get_open_shift(self, user_id: uuid.UUID, branch_id: uuid.UUID) -> Shift | None:
        stmt = select(Shift).where(Shift.user_id == user_id, Shift.branch_id == branch_id, Shift.status == "open")
        return self.db.execute(stmt).scalars().first()

    def add(self, shift: Shift) -> Shift:
        self.db.add(shift)
        self.db.flush()
        return shift

    def sum_cash_payments(self, shift_id: uuid.UUID) -> float:
        stmt = select(Payment).where(Payment.shift_id == shift_id, Payment.method == "cash")
        return float(sum(float(p.amount) for p in self.db.execute(stmt).scalars()))

    def list(self, organization_id: uuid.UUID, branch_id: uuid.UUID, limit: int = 20) -> list[Shift]:
        stmt = (
            select(Shift)
            .where(Shift.organization_id == organization_id, Shift.branch_id == branch_id)
            .order_by(Shift.opened_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars())
