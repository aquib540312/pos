import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, org_fk


class Organization(Base, UUIDPKMixin, TimestampMixin):
    """The tenant. Everything else hangs off an organization_id."""

    __tablename__ = "organizations"

    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(15), unique=True)
    pan: Mapped[str | None] = mapped_column(String(10))
    default_state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    branches: Mapped[list["Branch"]] = relationship(back_populates="organization")


class Branch(Base, UUIDPKMixin, TimestampMixin):
    """A physical outlet/store. Place-of-supply for POS sales is normally the
    branch's state, which is what drives CGST+SGST vs IGST (see gst module)."""

    __tablename__ = "branches"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_branch_org_code"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="grocery"
    )  # grocery|supermarket|medical|electronics|garment|restaurant
    gstin: Mapped[str | None] = mapped_column(String(15))
    state_code: Mapped[str] = mapped_column(String(2), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="branches")
    warehouses: Mapped[list["Warehouse"]] = relationship(back_populates="branch")


class Warehouse(Base, UUIDPKMixin, TimestampMixin):
    """Stock location. A branch usually has one warehouse (the shop floor +
    backroom treated as one), but multi-warehouse branches are supported."""

    __tablename__ = "warehouses"
    __table_args__ = (UniqueConstraint("branch_id", "code", name="uq_warehouse_branch_code"),)

    branch_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("branches.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    branch: Mapped["Branch"] = relationship(back_populates="warehouses")
