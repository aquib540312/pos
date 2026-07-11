from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from sync_agent.config import SyncAgentConfig
from sync_agent.domain.repositories import AuditLogRepository, SyncJournalRepository
from sync_agent.domain.transport import AuthenticationError, TransportError
from sync_agent.services.sync_service import SyncService

logger = logging.getLogger("sync_agent.worker")


@dataclass
class WorkerState:
    """A snapshot of the worker's own health, independent of what's in
    the local database -- consumed by the status dashboard alongside the
    queue/conflict counts."""

    running: bool = False
    last_cycle_at: float | None = None
    last_success_at: float | None = None
    last_error: str | None = None
    consecutive_failures: int = 0
    current_backoff_seconds: float = 0.0
    needs_reauth: bool = False


class SyncWorker:
    """Runs push+pull on a configurable interval in a background thread,
    with exponential backoff on failure and a fast-reconnect probe so a
    terminal that comes back online doesn't have to wait out a long
    backoff before syncing again.

    Crash recovery: `start()` always calls `recover_from_crash()` first,
    which closes out any sync_journal row left open by a process that
    died mid-cycle (killed, power loss, OS crash) -- there is deliberately
    no attempt to resume the exact in-flight HTTP call; the next full
    cycle simply runs from scratch, which is safe because push is
    idempotent (client_operation_id) and pull is cursor-based (nothing
    to lose by re-requesting from the same cursor).
    """

    def __init__(
        self,
        sync_service: SyncService,
        config: SyncAgentConfig,
        audit_log: AuditLogRepository,
        journal: SyncJournalRepository,
        sleep_fn=time.sleep,
        monotonic_fn=time.monotonic,
    ):
        self.sync_service = sync_service
        self.config = config
        self.audit_log = audit_log
        self.journal = journal
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn

        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._backoff_seconds = config.retry_initial_backoff_seconds
        self.state = WorkerState()

    # -- Crash recovery ------------------------------------------------------

    def recover_from_crash(self) -> None:
        for entry in self.journal.find_incomplete_cycles():
            self.journal.end_cycle(entry.id, success=False)
            self.audit_log.append(
                "sync.crash_recovered", {"cycle_type": entry.cycle_type, "started_at": entry.started_at}
            )
            logger.warning("Recovered incomplete %s cycle started at %s", entry.cycle_type, entry.started_at)

    # -- One cycle -----------------------------------------------------------

    def run_once(self) -> bool:
        """Runs one push+pull cycle. Returns True on success. Raises
        AuthenticationError unmodified -- that's not something retrying
        with backoff can fix, the caller (the loop) stops auto-retrying
        and waits for `force_sync()` after credentials are fixed."""
        self.state.last_cycle_at = self._monotonic()
        try:
            self.sync_service.push_pending()
            self.sync_service.pull_all()
        except AuthenticationError as exc:
            self.state.last_error = str(exc)
            self.state.needs_reauth = True
            self.audit_log.append("sync.auth_error", {"error": str(exc)})
            raise
        except TransportError as exc:
            self.state.last_error = str(exc)
            self.state.consecutive_failures += 1
            self.audit_log.append(
                "sync.transport_error", {"error": str(exc), "consecutive_failures": self.state.consecutive_failures}
            )
            return False

        self.state.last_success_at = self._monotonic()
        self.state.last_error = None
        self.state.consecutive_failures = 0
        self.state.needs_reauth = False
        self._backoff_seconds = self.config.retry_initial_backoff_seconds
        return True

    # -- Manual control --------------------------------------------------

    def force_sync(self) -> None:
        """Wakes the loop immediately instead of waiting out the current
        interval or backoff -- e.g. a cashier presses "Sync now"."""
        self._wake_event.set()

    def start(self) -> None:
        if self._thread is not None:
            return
        self.recover_from_crash()
        self._stop_event.clear()
        self.state.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="sync-agent-worker")
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop_event.set()
        self._wake_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        self.state.running = False

    # -- Internal loop ------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                success = self.run_once()
            except AuthenticationError:
                # Needs a human to re-register/refresh credentials --
                # keep the worker alive (force_sync() after they fix it
                # should work without a restart) but stop hammering the
                # server with a request that will keep failing the
                # same way.
                success = False
                wait_seconds = self.config.sync_interval_seconds
                self._wait(wait_seconds, probe_reconnect=False)
                continue

            if success:
                wait_seconds = self.config.sync_interval_seconds
                self._wait(wait_seconds, probe_reconnect=False)
            else:
                wait_seconds = self._backoff_seconds
                self._backoff_seconds = min(
                    self._backoff_seconds * self.config.retry_backoff_multiplier,
                    self.config.retry_max_backoff_seconds,
                )
                self.state.current_backoff_seconds = self._backoff_seconds
                self._wait(wait_seconds, probe_reconnect=True)

    def _wait(self, timeout: float, probe_reconnect: bool) -> None:
        """Sleeps up to `timeout`, but returns early if `force_sync()` is
        called, or -- while backing off after a failure -- as soon as a
        cheap reachability probe suggests the network is back, instead of
        always waiting out the full (possibly minutes-long) backoff."""
        if not probe_reconnect:
            if self._wake_event.wait(timeout=timeout):
                self._wake_event.clear()
            return

        deadline = self._monotonic() + timeout
        poll_interval = min(self.config.reconnect_check_interval_seconds, timeout) or timeout
        while self._monotonic() < deadline and not self._stop_event.is_set():
            remaining = deadline - self._monotonic()
            if self._wake_event.wait(timeout=min(poll_interval, remaining)):
                self._wake_event.clear()
                return
            if self.sync_service.transport.ping():
                return
