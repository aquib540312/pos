from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, org_fk

if TYPE_CHECKING:
    from app.models.catalog import Product


class CuttingOrder(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "cutting_orders"

    organization_id: Mapped[uuid.UUID] = org_fk()
    source_product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    input_weight: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)
    butcher_name: Mapped[str | None] = mapped_column(String(255))
    cutting_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    notes: Mapped[str | None] = mapped_column(String(500))

    items: Mapped[list["CuttingOrderItem"]] = relationship(back_populates="cutting_order")
    source_product: Mapped["Product"] = relationship(foreign_keys=[source_product_id])


class CuttingOrderItem(Base, UUIDPKMixin):
    __tablename__ = "cutting_order_items"

    cutting_order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("cutting_orders.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    output_weight: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)
    waste_weight: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False, default=0)

    cutting_order: Mapped["CuttingOrder"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(foreign_keys=[product_id])
