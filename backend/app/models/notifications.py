import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import GUID, UUIDPKMixin, org_fk


class AppNotification(Base, UUIDPKMixin):
    """An in-app notification / alert -- the landing point for dashboard
    alerts (low stock, expiring batches, sync conflicts, shift reminders).
    These are stored per-org and optionally per-user; unread count drives a
    bell badge in the UI. Distinct from the adapters-only outbound
    notification channel (SMS/email) which is fire-and-forget and has no
    inbox."""

    __tablename__ = "app_notifications"

    organization_id: Mapped[uuid.UUID] = org_fk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False)  # low_stock|expiry|sync_conflict|shift|info
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(String(1000))
    reference_type: Mapped[str | None] = mapped_column(String(30))
    reference_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)