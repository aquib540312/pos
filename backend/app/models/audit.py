import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import GUID, UUIDPKMixin, org_fk


class AuditLog(Base, UUIDPKMixin):
    """Who did what to which record, when. Written by a service-layer
    decorator/helper on every create/update/delete of a sensitive entity
    (users, roles, price changes, stock adjustments, cancellations) -- never
    relied upon as the sole record of financial truth (that's the
    stock/journal ledgers), this is for "who pressed the button"."""

    __tablename__ = "audit_logs"

    organization_id: Mapped[uuid.UUID] = org_fk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "product.update"
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    details: Mapped[str | None] = mapped_column(String(2000))  # JSON-encoded diff/snapshot
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
