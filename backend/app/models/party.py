import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, org_fk


class Customer(Base, UUIDPKMixin, TimestampMixin):
    """Customer profile for Saudi Beef Wholesale + Retail business.
    Supports Arabic names, VAT numbers, CR numbers, and multiple price levels."""

    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("organization_id", "phone", name="uq_customer_org_phone"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_arabic: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    vat_number: Mapped[str | None] = mapped_column(String(15))  # Saudi VAT number (instead of GSTIN)
    cr_number: Mapped[str | None] = mapped_column(String(20))  # Commercial Registration number
    state_code: Mapped[str | None] = mapped_column(String(2))
    address: Mapped[str | None] = mapped_column(String(500))

    # Customer type: walk_in, restaurant, hotel, catering, regular, wholesale
    customer_type: Mapped[str] = mapped_column(String(30), nullable=False, default="walk_in")
    # Price level: retail, wholesale, restaurant, vip, custom
    price_level: Mapped[str] = mapped_column(String(20), nullable=False, default="retail")

    is_credit_customer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    credit_limit: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    credit_balance: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outstanding_balance: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    total_purchases: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    last_purchase_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    loyalty_points_balance: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Supplier(Base, UUIDPKMixin, TimestampMixin):
    """Supplier profile for Saudi Beef Wholesale + Retail business.
    Supports Arabic names, VAT numbers, and CR numbers."""

    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_supplier_org_name"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_arabic: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    vat_number: Mapped[str | None] = mapped_column(String(15))  # Saudi VAT number
    cr_number: Mapped[str | None] = mapped_column(String(20))  # Commercial Registration number
    state_code: Mapped[str | None] = mapped_column(String(2))
    address: Mapped[str | None] = mapped_column(String(500))
    payable_balance: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SupplierPayment(Base, UUIDPKMixin, TimestampMixin):
    """A standalone payment against a supplier's running payable balance
    (reduces Accounts Payable) -- the purchase-side mirror of a customer
    credit collection. Debits AP, credits cash/bank in the ledger, and the
    supplier's payable_balance is reduced by the applied amount."""

    __tablename__ = "supplier_payments"

    organization_id: Mapped[uuid.UUID] = org_fk()
    supplier_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("suppliers.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False, default="bank")  # cash|bank|card|upi
    reference: Mapped[str | None] = mapped_column(String(120))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255))
