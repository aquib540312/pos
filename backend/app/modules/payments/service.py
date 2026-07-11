from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, NotFoundError
from app.models.payments import PaymentGatewayTransaction
from app.modules.payments.adapters import PaymentGatewayAdapter, RazorpayAdapter
from app.modules.payments.repository import PaymentGatewayRepository

# Events that mean "the customer's money has arrived" for a UPI QR --
# Razorpay fires qr_code.credited for the QR-specific flow; payment.captured
# also arrives for the underlying payment. Either is sufficient to mark paid.
_PAID_EVENTS = {"qr_code.credited", "payment.captured"}


class PaymentGatewayService:
    def __init__(self, db: Session, settings: Settings | None = None, adapter: PaymentGatewayAdapter | None = None):
        self.db = db
        self.transactions = PaymentGatewayRepository(db)
        self.adapter: PaymentGatewayAdapter = adapter or RazorpayAdapter(settings or get_settings())

    def create_upi_qr(
        self, organization_id: uuid.UUID, amount: float, receipt_reference: str
    ) -> PaymentGatewayTransaction:
        result = self.adapter.create_upi_qr(amount, receipt_reference)
        return self.transactions.add(
            PaymentGatewayTransaction(
                organization_id=organization_id,
                provider="razorpay",
                gateway_reference=result.gateway_reference,
                amount=amount,
                status="created",
                receipt_reference=receipt_reference,
                qr_image_url=result.image_url,
            )
        )

    def get_status(self, transaction_id: uuid.UUID) -> PaymentGatewayTransaction:
        transaction = self.transactions.get(transaction_id)
        if transaction is None:
            raise NotFoundError(f"Payment transaction {transaction_id} not found")
        return transaction

    def cancel(self, transaction_id: uuid.UUID) -> PaymentGatewayTransaction:
        transaction = self.get_status(transaction_id)
        self.adapter.close_qr(transaction.gateway_reference)
        transaction.status = "closed"
        self.db.flush()
        return transaction

    def handle_webhook(self, raw_body: bytes, signature: str) -> PaymentGatewayTransaction | None:
        """Verifies the request actually came from Razorpay (HMAC over the
        raw body, never trust an unsigned payload) before touching any
        transaction. Returns the updated transaction, or None if the event
        wasn't a payment-confirmation event or referenced an unknown QR
        (e.g. a webhook retry after we've already processed it, or a QR
        from a different environment) -- both are legitimate no-ops, not
        errors."""
        if not self.adapter.verify_webhook_signature(raw_body, signature):
            raise AuthenticationError("Invalid Razorpay webhook signature")

        payload = json.loads(raw_body)
        if payload.get("event") not in _PAID_EVENTS:
            return None

        entities = payload.get("payload", {})
        qr_entity = entities.get("qr_code", {}).get("entity", {})
        payment_entity = entities.get("payment", {}).get("entity", {})
        gateway_reference = qr_entity.get("id") or payment_entity.get("qr_code_id")
        if not gateway_reference:
            return None

        transaction = self.transactions.get_by_gateway_reference(gateway_reference)
        if transaction is None or transaction.status == "paid":
            return transaction

        transaction.status = "paid"
        transaction.paid_at = datetime.now(timezone.utc)
        transaction.gateway_payment_id = payment_entity.get("id")
        self.db.flush()
        return transaction
