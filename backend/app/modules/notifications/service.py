import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notifications import AppNotification


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self, organization_id: uuid.UUID, category: str, title: str,
        body: str | None = None, user_id: uuid.UUID | None = None,
        reference_type: str | None = None, reference_id: uuid.UUID | None = None,
    ) -> AppNotification:
        notification = AppNotification(
            organization_id=organization_id,
            user_id=user_id,
            category=category,
            title=title,
            body=body,
            reference_type=reference_type,
            reference_id=reference_id,
            is_read=False,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(notification)
        self.db.flush()
        return notification

    def sync_alerts(
        self, organization_id: uuid.UUID,
        low_stock: list[tuple[uuid.UUID, str, str, float]],
        expiring: list[tuple[uuid.UUID, str, str, str, float]],
    ) -> int:
        """Reconcile the dashboard alert rows into in-app notifications,
        deduplicated per reference (a product keeps one unread low-stock
        alert until it's resolved; re-creating it each dashboard call would
        spam the inbox). Returns how many notifications were created."""
        created = 0
        for reference_id, name, sku, qty in low_stock:
            exists = self.db.execute(
                select(func.count()).select_from(AppNotification).where(
                    AppNotification.organization_id == organization_id,
                    AppNotification.category == "low_stock",
                    AppNotification.reference_type == "product",
                    AppNotification.reference_id == reference_id,
                )
            ).scalar_one()
            if exists:
                continue
            self.create(
                organization_id, "low_stock",
                f"Low stock: {name}",
                f"Only {qty:.0f} on hand, reorder level reached. SKU {sku}.",
                reference_type="product", reference_id=reference_id,
            )
            created += 1
        for reference_id, name, sku, batch_number, days in expiring:
            exists = self.db.execute(
                select(func.count()).select_from(AppNotification).where(
                    AppNotification.organization_id == organization_id,
                    AppNotification.category == "expiry",
                    AppNotification.reference_type == "product",
                    AppNotification.reference_id == reference_id,
                )
            ).scalar_one()
            if exists:
                continue
            self.create(
                organization_id, "expiry",
                f"Expiring stock: {name}",
                f"Batch {batch_number} expires within {days:.0f} day(s). SKU {sku}.",
                reference_type="product", reference_id=reference_id,
            )
            created += 1
        return created

    def list(self, organization_id: uuid.UUID, user_id: uuid.UUID | None, limit: int = 50) -> list[AppNotification]:
        stmt = (
            select(AppNotification)
            .where(AppNotification.organization_id == organization_id)
            .order_by(AppNotification.created_at.desc())
            .limit(limit)
        )
        rows = list(self.db.execute(stmt).scalars())
        if user_id is None:
            return rows
        return [n for n in rows if n.user_id is None or n.user_id == user_id]

    def unread_count(self, organization_id: uuid.UUID) -> int:
        count = self.db.execute(
            select(func.count()).select_from(AppNotification).where(
                AppNotification.organization_id == organization_id, AppNotification.is_read.is_(False)
            )
        ).scalar_one()
        return int(count)

    def mark_read(self, organization_id: uuid.UUID, notification_id: uuid.UUID) -> AppNotification | None:
        notification = self.db.get(AppNotification, notification_id)
        if notification is None or notification.organization_id != organization_id:
            return None
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = datetime.now(timezone.utc)
            self.db.flush()
        return notification

    def mark_all_read(self, organization_id: uuid.UUID) -> int:
        rows = list(
            self.db.execute(
                select(AppNotification).where(
                    AppNotification.organization_id == organization_id, AppNotification.is_read.is_(False)
                )
            ).scalars()
        )
        now = datetime.now(timezone.utc)
        for n in rows:
            n.is_read = True
            n.read_at = now
        self.db.flush()
        return len(rows)
