import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, org_fk


class WasteEntry(Base, UUIDPKMixin, TimestampMixin):
    """Waste/spoilage tracking for beef products.
    Records financial loss from spoilage, expiry, damage, cutting loss, etc."""

    __tablename__ = "waste_entries"

    organization_id: Mapped[uuid.UUID] = org_fk()
    warehouse_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("warehouses.id"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("product_batches.id"), nullable=True)

    waste_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    total_cost: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    # Reason: spoilage, expired, damaged, cutting_loss, bone_loss, processing_loss, other
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)

    product: Mapped["Product"] = relationship()
