import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, org_fk


class LoyaltyTransaction(Base, UUIDPKMixin):
    """Append-only ledger of loyalty point accrual/redemption, mirroring the
    stock-ledger pattern -- Customer.loyalty_points_balance is the cached
    running total, this table is the source of truth for audits."""

    __tablename__ = "loyalty_transactions"

    organization_id: Mapped[uuid.UUID] = org_fk()
    customer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("customers.id"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("sales_invoices.id"), nullable=True)
    points_delta: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)  # signed
    reason: Mapped[str] = mapped_column(String(20), nullable=False)  # earn|redeem|expire|adjustment
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Coupon(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "coupons"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_coupon_org_code"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    discount_type: Mapped[str] = mapped_column(String(10), nullable=False)  # percent|flat
    discount_value: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    min_order_value: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    max_redemptions: Mapped[int | None] = mapped_column()
    times_redeemed: Mapped[int] = mapped_column(default=0)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GiftCard(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "gift_cards"
    __table_args__ = (UniqueConstraint("organization_id", "card_number", name="uq_gift_card_org_number"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    card_number: Mapped[str] = mapped_column(String(40), nullable=False)
    initial_value: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    balance: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    issued_to_customer_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("customers.id"), nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    transactions: Mapped[list["GiftCardTransaction"]] = relationship(back_populates="gift_card")


class GiftCardTransaction(Base, UUIDPKMixin):
    __tablename__ = "gift_card_transactions"

    gift_card_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("gift_cards.id"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("sales_invoices.id"), nullable=True)
    amount_delta: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)  # negative on redemption
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    gift_card: Mapped["GiftCard"] = relationship(back_populates="transactions")
