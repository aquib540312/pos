import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, branch_fk, org_fk

if TYPE_CHECKING:
    from app.models.billing import Payment


class Quotation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "quotations"

    organization_id: Mapped[uuid.UUID] = org_fk()
    branch_id: Mapped[uuid.UUID] = branch_fk()
    customer_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("customers.id"), nullable=True)
    quotation_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    quotation_date: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft|sent|converted|expired
    grand_total: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    # Set only once status becomes "converted" -- traces which real sale
    # this quotation turned into (see QuotationService.convert_to_sale).
    converted_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("sales_invoices.id"), nullable=True
    )

    items: Mapped[list["QuotationItem"]] = relationship(back_populates="quotation")


class QuotationItem(Base, UUIDPKMixin):
    __tablename__ = "quotation_items"

    quotation_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("quotations.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)

    quotation: Mapped["Quotation"] = relationship(back_populates="items")


class SalesInvoice(Base, UUIDPKMixin, TimestampMixin):
    """A posted sale is immutable (see ARCHITECTURE.md #3) -- corrections go
    through SalesReturn, never UPDATE. `status="draft"` exists only for the
    brief window of cart-building before checkout; once status becomes
    "posted" the row and its items must not be mutated again."""

    __tablename__ = "sales_invoices"

    organization_id: Mapped[uuid.UUID] = org_fk()
    branch_id: Mapped[uuid.UUID] = branch_fk()
    customer_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("customers.id"), nullable=True)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("shifts.id"), nullable=True)

    invoice_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    invoice_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    place_of_supply_state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    is_inter_state: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Snapshotted from Customer.gstin at posting time, never re-read from
    # the customer later (ARCHITECTURE.md #3: posted rows are immutable,
    # and a customer's GSTIN can change after this invoice was filed).
    # NULL means this was a B2C sale (walk-in/unregistered consumer);
    # GSTR-1 Table 4 (B2B) vs Table 7 (B2C small) is decided by this
    # column, not by re-checking whether customer_id has a GSTIN today.
    customer_gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)

    subtotal: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    discount_total: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    taxable_total: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    cgst_total: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    sgst_total: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    igst_total: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    cess_total: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    round_off: Mapped[float] = mapped_column(Numeric(6, 2, asdecimal=False), nullable=False, default=0)
    grand_total: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)

    is_credit_sale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="posted")  # posted|cancelled
    loyalty_points_earned: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    loyalty_points_redeemed: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    coupon_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    coupon_discount_amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)

    items: Mapped[list["SalesInvoiceItem"]] = relationship(back_populates="invoice")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="invoice")


class SalesInvoiceItem(Base, UUIDPKMixin):
    """Every GST amount is stored, never recomputed later -- reports read
    these columns directly (see ARCHITECTURE.md #4)."""

    __tablename__ = "sales_invoice_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("sales_invoices.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("product_batches.id"), nullable=True)
    hsn_code_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("hsn_codes.id"), nullable=True)

    quantity: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    taxable_value: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    tax_rate_percent: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=False, default=0)
    cgst_amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    sgst_amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    igst_amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    cess_amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)

    invoice: Mapped["SalesInvoice"] = relationship(back_populates="items")


class SalesReturn(Base, UUIDPKMixin, TimestampMixin):
    """A return or exchange against a posted invoice. Exchange is modeled as
    a SalesReturn (for the returned item) linked 1:1 with a new
    SalesInvoice (for the replacement item), rather than a special-cased
    "exchange" transaction type -- this keeps both sides of an exchange as
    normal, auditable, immutable postings."""

    __tablename__ = "sales_returns"

    organization_id: Mapped[uuid.UUID] = org_fk()
    branch_id: Mapped[uuid.UUID] = branch_fk()
    original_invoice_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("sales_invoices.id"), nullable=False, index=True
    )
    exchange_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("sales_invoices.id"), nullable=True
    )
    return_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    return_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    refund_total: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    refund_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="cash")

    items: Mapped[list["SalesReturnItem"]] = relationship(back_populates="sales_return")


class SalesReturnItem(Base, UUIDPKMixin):
    __tablename__ = "sales_return_items"

    sales_return_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("sales_returns.id"), nullable=False, index=True
    )
    original_invoice_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("sales_invoice_items.id"), nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)
    taxable_value: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    cgst_amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    sgst_amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    igst_amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)

    sales_return: Mapped["SalesReturn"] = relationship(back_populates="items")
