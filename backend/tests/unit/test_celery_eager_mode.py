"""Render's free plan (and possibly other hosts) can't run a Celery
worker at all -- Settings.celery_task_always_eager is how the app runs
correctly anyway, executing queued tasks synchronously in-process instead
of handing them to a worker that will never exist. These tests exercise
the real Celery eager-execution path (not a mock of .delay itself), to
prove that flip actually works, not just that the config value is stored.
"""

from app.celery_app import celery_app
from app.core.config import Settings
from app.modules.notifications import tasks as notification_tasks
from app.modules.printing import tasks as printing_tasks


def test_default_settings_do_not_enable_eager_mode():
    assert Settings().celery_task_always_eager is False


def test_celery_conf_defaults_to_non_eager_matching_settings():
    """The normal (docker-compose, a real worker present) case: dispatch
    stays decoupled from the request unless explicitly overridden."""
    assert celery_app.conf.task_always_eager is False
    assert celery_app.conf.task_eager_propagates is False


def test_eager_mode_runs_notification_task_synchronously(monkeypatch):
    calls = []
    monkeypatch.setattr(
        notification_tasks, "send_notification", lambda channel, to, message: calls.append((channel, to, message))
    )

    celery_app.conf.task_always_eager = True
    try:
        result = notification_tasks.send_notification_task.delay("sms", "9990001111", "hello")
    finally:
        celery_app.conf.task_always_eager = False

    # Ran inline, synchronously -- no worker was needed to process it.
    assert calls == [("sms", "9990001111", "hello")]
    assert result.successful()


def test_eager_mode_runs_print_task_synchronously(monkeypatch):
    calls = []
    monkeypatch.setattr(printing_tasks.PrintService, "print_invoice", lambda self, payload: calls.append(payload) or True)

    celery_app.conf.task_always_eager = True
    try:
        result = printing_tasks.print_receipt_task.delay({"invoice_number": "INV/TEST"})
    finally:
        celery_app.conf.task_always_eager = False

    assert calls == [{"invoice_number": "INV/TEST"}]
    assert result.successful()
    assert result.get() is True
