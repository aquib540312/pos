from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "pos",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.modules.notifications.tasks", "app.modules.printing.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # See Settings.celery_task_always_eager -- when true (no worker
    # process available, e.g. Render's free plan), .delay() runs the task
    # synchronously in the caller instead of hand-off to a worker.
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=settings.celery_task_always_eager,
)
