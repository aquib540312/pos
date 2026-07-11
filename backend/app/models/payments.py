import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, org_fk


class PaymentGatewayTransaction(Base, UUIDPKMixin, TimestampMixin):
    """Tracks a UPI QR (or other gateway) payment request from creation
    through confirmation, independent of the eventual SalesInvoice.

    A physical POS collects money *before* the cashier finalizes the sale
    record (customer scans and pays, then the till shows "paid" and the
    cashier taps complete) -- so this is a separate, short-lived tracked
    object, not a field on SalesInvoice/Payment. Once confirmed, its
    gateway_reference is what gets passed as the `reference` on the normal
    Payment row created by the ordinary POST /sales call; no changes to
    the core sales flow were needed to support this.
    """

    __tablename__ = "payment_gateway_transactions"

    organization_id: Mapped[uuid.UUID] = org_fk()
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="razorpay")
    gateway_reference: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  # e.g. Razorpay qr_code id
    amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="created")  # created|paid|closed|expired
    receipt_reference: Mapped[str | None] = mapped_column(String(60), nullable=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("sales_invoices.id"), nullable=True)
    qr_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
