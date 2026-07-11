import uuid

from sqlalchemy import Boolean, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, org_fk


class Customer(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("organization_id", "phone", name="uq_customer_org_phone"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    gstin: Mapped[str | None] = mapped_column(String(15))
    state_code: Mapped[str | None] = mapped_column(String(2))
    address: Mapped[str | None] = mapped_column(String(500))

    is_credit_customer: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    credit_limit: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    credit_balance: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)

    loyalty_points_balance: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Supplier(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_supplier_org_name"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    gstin: Mapped[str | None] = mapped_column(String(15))
    state_code: Mapped[str | None] = mapped_column(String(2))
    address: Mapped[str | None] = mapped_column(String(500))
    payable_balance: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
