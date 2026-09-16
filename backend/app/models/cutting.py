import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, org_fk


class CuttingOrder(Base, UUIDPKMixin, TimestampMixin):
    """Butcher/cutting workflow for processing beef carcasses into cuts.
    Tracks input carcass and output cuts with weight conversion."""

    __tablename__ = "cutting_orders"

    organization_id: Mapped[uuid.UUID] = org_fk()
    warehouse_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("warehouses.id"), nullable=False)

    cutting_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    cutting_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Source product (e.g. beef carcass)
    source_product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    source_batch_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("product_batches.id"), nullable=True)
    input_weight: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft|completed|cancelled
    notes: Mapped[str | None] = mapped_column(String(500))
    butcher_name: Mapped[str | None] = mapped_column(String(100))

    items: Mapped[list["CuttingOrderItem"]] = relationship(back_populates="cutting_order")
    source_product: Mapped["Product"] = relationship(foreign_keys=[source_product_id])


class CuttingOrderItem(Base, UUIDPKMixin):
    """Individual cut output from a cutting order.
    Each cut becomes a separate product in inventory."""

    __tablename__ = "cutting_order_items"

    cutting_order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("cutting_orders.id"), nullable=False, index=True
    )
    # Output product (the cut, e.g. tenderloin, ribeye)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    output_weight: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)
    # Waste/bone/fat from this cut
    waste_weight: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False, default=0)

    cutting_order: Mapped["CuttingOrder"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(foreign_keys=[product_id])
