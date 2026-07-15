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
    # Without these two settings, .delay() blocks for ~20s before raising
    # when Redis is unreachable -- every caller (checkout receipt SMS,
    # password-reset email) wraps .delay() in a broad except specifically
    # so a broker outage can't break the request, but a 20s hang defeats
    # that just as badly as an exception would. Two separate Redis
    # connections are involved and both need bounding: broker_transport_options
    # bounds the retry loop on the broker connection (Celery's documented
    # fix for this exact redis-broker scenario); task_ignore_result skips
    # the result backend entirely, which turned out to be the slower of
    # the two -- nothing here ever calls .get() on a result, so there was
    # never a reason to write one. Together: <0.1s to fail instead of ~20s.
    broker_transport_options={"max_retries": 1, "interval_start": 0, "interval_step": 0.2, "interval_max": 0.2},
    task_publish_retry=False,
    task_ignore_result=True,
)
