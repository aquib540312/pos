from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.payments import PaymentGatewayTransaction


class PaymentGatewayRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, transaction: PaymentGatewayTransaction) -> PaymentGatewayTransaction:
        self.db.add(transaction)
        self.db.flush()
        return transaction

    def get(self, transaction_id: uuid.UUID) -> PaymentGatewayTransaction | None:
        return self.db.get(PaymentGatewayTransaction, transaction_id)

    def get_by_gateway_reference(self, gateway_reference: str) -> PaymentGatewayTransaction | None:
        stmt = select(PaymentGatewayTransaction).where(
            PaymentGatewayTransaction.gateway_reference == gateway_reference
        )
        return self.db.execute(stmt).scalars().first()
