import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.notifications.schemas import (
    AppNotificationResponse,
    SendNotificationRequest,
    UnreadCountResponse,
)
from app.modules.notifications.service import NotificationService
from app.modules.notifications.tasks import send_notification_task

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


@router.post("/send", status_code=status.HTTP_202_ACCEPTED)
def send_notification(
    payload: SendNotificationRequest, user: User = Depends(require_permission(Perm.SALES_CREATE))
) -> dict[str, str]:
    """Queues a notification job on Celery. Requires the Celery worker and
    Redis broker to be running (see docker-compose.yml) -- not exercised by
    the pytest suite, which has no broker available, by design."""
    send_notification_task.delay(payload.channel, payload.to, payload.message)
    return {"status": "queued"}


@router.get("", response_model=list[AppNotificationResponse])
def list_in_app_notifications(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Recent in-app notifications (low stock, expiring batches, sync
    conflicts, shift reminders) for the caller's organization. Counts pull
    on the bell badge; every signed-in staff sees the org inbox."""
    return NotificationService(db).list(user.organization_id, user.id, limit)


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return UnreadCountResponse(unread_count=NotificationService(db).unread_count(user.organization_id))


@router.post("/{notification_id}/read", response_model=AppNotificationResponse)
def mark_notification_read(
    notification_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    notification = NotificationService(db).mark_read(user.organization_id, notification_id)
    if notification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Notification {notification_id} not found")
    db.commit()
    return notification


@router.post("/read-all", status_code=status.HTTP_200_OK)
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, int]:
    marked = NotificationService(db).mark_all_read(user.organization_id)
    db.commit()
    return {"marked": marked}
