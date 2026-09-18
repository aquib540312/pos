import uuid

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, org_fk


class WasteEntry(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "waste_entries"

    organization_id: Mapped[uuid.UUID] = org_fk()
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    total_cost: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)

    product: Mapped["Product"] = relationship()
