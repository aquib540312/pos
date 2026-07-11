from fastapi import APIRouter, Depends, status

from app.core.deps import require_permission
from app.core.permissions import Perm
from app.models.rbac import User
from app.modules.notifications.schemas import SendNotificationRequest
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
