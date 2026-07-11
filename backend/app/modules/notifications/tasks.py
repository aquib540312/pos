from app.celery_app import celery_app
from app.modules.notifications.adapters import send_notification


@celery_app.task(name="notifications.send")
def send_notification_task(channel: str, to: str, message: str) -> None:
    """Runs off the request thread so a slow/unavailable SMS or WhatsApp
    provider can never add latency to (or fail) a checkout request."""
    send_notification(channel, to, message)
