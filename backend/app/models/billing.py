import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, branch_fk, org_fk

if TYPE_CHECKING:
    from app.models.sales import SalesInvoice


class Shift(Base, UUIDPKMixin, TimestampMixin):
    """A cashier's till session at a branch. Opening/closing cash counts are
    recorded here; `expected_closing_cash` is derived from opening_cash +
    cash payments during the shift, `counted_closing_cash` is what the
    cashier physically counted -- the difference (`cash_variance`) is the
    daily cash closing reconciliation figure."""

    __tablename__ = "shifts"

    organization_id: Mapped[uuid.UUID] = org_fk()
    branch_id: Mapped[uuid.UUID] = branch_fk()
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)

    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opening_cash: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    expected_closing_cash: Mapped[float | None] = mapped_column(Numeric(12, 2, asdecimal=False))
    counted_closing_cash: Mapped[float | None] = mapped_column(Numeric(12, 2, asdecimal=False))
    cash_variance: Mapped[float | None] = mapped_column(Numeric(12, 2, asdecimal=False))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")  # open|closed


class Payment(Base, UUIDPKMixin, TimestampMixin):
    """One tender line against an invoice. Multi-payment (split tender) is
    simply multiple Payment rows on one invoice; the sum must equal
    invoice.grand_total, enforced in the billing service, not the DB, since
    partial credit-sale payments are legitimate for credit customers (an
    invoice can be posted with less than full payment when
    is_credit_sale=True, and the customer's credit_balance absorbs the
    remainder)."""

    __tablename__ = "payments"

    organization_id: Mapped[uuid.UUID] = org_fk()
    invoice_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("sales_invoices.id"), nullable=False, index=True)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("shifts.id"), nullable=True)

    method: Mapped[str] = mapped_column(String(20), nullable=False)  # cash|card|upi|wallet|credit|gift_card
    amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))  # UPI txn id / card auth code

    invoice: Mapped["SalesInvoice"] = relationship("SalesInvoice", back_populates="payments")
