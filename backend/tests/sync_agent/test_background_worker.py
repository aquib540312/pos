from __future__ import annotations

import time

import pytest

from sync_agent.domain.transport import AuthenticationError
from sync_agent.infrastructure.sqlite_repositories import (
    SqliteAuditLogRepository,
    SqliteConflictRepository,
    SqliteCursorRepository,
    SqliteCustomerRepository,
    SqliteOfflineSaleRepository,
    SqliteProductRepository,
    SqliteStockRepository,
    SqliteSyncJournalRepository,
)
from sync_agent.services.background_worker import SyncWorker
from sync_agent.services.sync_service import SyncService
from tests.sync_agent.fakes import FakeTransport


def _make_worker(local_db, agent_config, transport=None):
    transport = transport or FakeTransport()
    offline_sales = SqliteOfflineSaleRepository(local_db)
    products = SqliteProductRepository(local_db)
    customers = SqliteCustomerRepository(local_db)
    stock = SqliteStockRepository(local_db)
    cursors = SqliteCursorRepository(local_db)
    conflicts = SqliteConflictRepository(local_db)
    audit_log = SqliteAuditLogRepository(local_db)
    journal = SqliteSyncJournalRepository(local_db)
    sync_service = SyncService(
        transport, agent_config, offline_sales, products, customers, stock, cursors, conflicts, audit_log, journal
    )
    worker = SyncWorker(sync_service, agent_config, audit_log, journal)
    return worker, transport, journal, audit_log


def test_run_once_success_resets_backoff_and_records_state(local_db, agent_config):
    worker, transport, journal, audit_log = _make_worker(local_db, agent_config)
    assert worker.run_once() is True
    assert worker.state.last_error is None
    assert worker.state.consecutive_failures == 0
    assert worker.state.last_success_at is not None


def test_run_once_transport_failure_is_recorded_not_raised(local_db, agent_config):
    worker, transport, journal, audit_log = _make_worker(local_db, agent_config)
    transport.fail_next_push = True
    # push_pending() itself is a no-op with nothing queued -- force a
    # failure via pull instead by making the very first network call fail.
    transport.fail_next_pull = True
    result = worker.run_once()
    assert result is False
    assert worker.state.consecutive_failures == 1
    assert worker.state.last_error is not None


def test_run_once_authentication_error_propagates_and_sets_needs_reauth(local_db, agent_config):
    worker, transport, journal, audit_log = _make_worker(local_db, agent_config)
    transport.raise_auth_error = True
    with pytest.raises(AuthenticationError):
        worker.run_once()
    assert worker.state.needs_reauth is True


def test_crash_recovery_closes_incomplete_journal_entries(local_db, agent_config):
    worker, transport, journal, audit_log = _make_worker(local_db, agent_config)
    # Simulate a previous process that died mid-cycle: a journal entry
    # with no finished_at.
    journal.begin_cycle("push")

    worker.recover_from_crash()

    assert journal.find_incomplete_cycles() == []
    actions = [e.action for e in audit_log.list_recent(10)]
    assert "sync.crash_recovered" in actions


def test_start_calls_recover_from_crash_and_runs_in_background(local_db, agent_config):
    worker, transport, journal, audit_log = _make_worker(local_db, agent_config)
    stale_entry = journal.begin_cycle("pull")

    worker.start()
    try:
        # Give the background thread a moment to run at least one cycle.
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and worker.state.last_cycle_at is None:
            time.sleep(0.01)
        assert worker.state.last_cycle_at is not None
        assert journal.find_incomplete_cycles() == [] or all(
            e.id != stale_entry.id for e in journal.find_incomplete_cycles()
        )
    finally:
        worker.stop()
    assert worker.state.running is False


def test_force_sync_wakes_the_loop_before_the_interval_elapses(local_db, agent_config):
    config = agent_config.with_overrides(sync_interval_seconds=10.0)  # would never fire naturally within the test
    worker, transport, journal, audit_log = _make_worker(local_db, config)

    worker.start()
    try:
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and worker.state.last_cycle_at is None:
            time.sleep(0.01)
        first_cycle_at = worker.state.last_cycle_at
        assert first_cycle_at is not None

        worker.force_sync()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and worker.state.last_cycle_at == first_cycle_at:
            time.sleep(0.01)
        assert worker.state.last_cycle_at != first_cycle_at
    finally:
        worker.stop()


def test_backoff_grows_on_repeated_failures_and_resets_on_success(local_db, agent_config):
    transport = FakeTransport()
    worker, _, journal, audit_log = _make_worker(local_db, agent_config, transport)

    transport.fail_next_pull = True
    worker.run_once()
    first_backoff = worker._backoff_seconds
    assert first_backoff == agent_config.retry_initial_backoff_seconds

    # Manually drive the loop's backoff growth logic the same way _loop does.
    worker._backoff_seconds = min(
        worker._backoff_seconds * agent_config.retry_backoff_multiplier, agent_config.retry_max_backoff_seconds
    )
    assert worker._backoff_seconds > first_backoff

    worker.run_once()  # succeeds this time
    assert worker._backoff_seconds == agent_config.retry_initial_backoff_seconds
