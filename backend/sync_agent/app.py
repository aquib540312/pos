from __future__ import annotations

from dataclasses import dataclass

from sync_agent.config import SyncAgentConfig
from sync_agent.domain.transport import SyncTransport
from sync_agent.infrastructure.db import LocalDatabase
from sync_agent.infrastructure.http_transport import HttpSyncTransport
from sync_agent.infrastructure.sqlite_repositories import (
    SqliteAuditLogRepository,
    SqliteConflictRepository,
    SqliteCursorRepository,
    SqliteCustomerRepository,
    SqliteOfflineSaleRepository,
    SqliteProductRepository,
    SqliteStockRepository,
    SqliteSyncJournalRepository,
    SqliteTerminalMetaRepository,
)
from sync_agent.services.background_worker import SyncWorker
from sync_agent.services.offline_sales_queue import OfflineSalesQueueService
from sync_agent.services.status import StatusService
from sync_agent.services.sync_service import SyncService


@dataclass
class SyncAgentApp:
    """Composition root: wires the concrete SQLite repositories and HTTP
    transport behind the same domain interfaces the services depend on.
    Swapping either -- a different local storage engine, a non-HTTP
    transport -- means constructing this differently, not changing any
    service code."""

    config: SyncAgentConfig
    db: LocalDatabase
    transport: SyncTransport
    offline_sales: SqliteOfflineSaleRepository
    products: SqliteProductRepository
    customers: SqliteCustomerRepository
    stock: SqliteStockRepository
    cursors: SqliteCursorRepository
    conflicts: SqliteConflictRepository
    audit_log: SqliteAuditLogRepository
    journal: SqliteSyncJournalRepository
    terminal_meta: SqliteTerminalMetaRepository
    sales_queue: OfflineSalesQueueService
    sync_service: SyncService
    worker: SyncWorker
    status_service: StatusService

    def close(self) -> None:
        if hasattr(self.transport, "close"):
            self.transport.close()
        self.db.close()


def build_app(config: SyncAgentConfig, transport: SyncTransport | None = None) -> SyncAgentApp:
    db = LocalDatabase(
        db_path=config.db_path,
        encryption_key=config.db_encryption_key,
        allow_unencrypted=config.allow_unencrypted_storage,
    )
    offline_sales = SqliteOfflineSaleRepository(db)
    products = SqliteProductRepository(db)
    customers = SqliteCustomerRepository(db)
    stock = SqliteStockRepository(db)
    cursors = SqliteCursorRepository(db)
    conflicts = SqliteConflictRepository(db)
    audit_log = SqliteAuditLogRepository(db)
    journal = SqliteSyncJournalRepository(db)
    terminal_meta = SqliteTerminalMetaRepository(db)

    if transport is None:
        transport = HttpSyncTransport(
            config.server_base_url, config.terminal_api_key, config.request_timeout_seconds
        )

    sales_queue = OfflineSalesQueueService(offline_sales, audit_log)
    sync_service = SyncService(
        transport, config, offline_sales, products, customers, stock, cursors, conflicts, audit_log, journal
    )
    worker = SyncWorker(sync_service, config, audit_log, journal)
    status_service = StatusService(worker.state, offline_sales, conflicts, products, customers, stock, audit_log)

    return SyncAgentApp(
        config=config, db=db, transport=transport, offline_sales=offline_sales, products=products,
        customers=customers, stock=stock, cursors=cursors, conflicts=conflicts, audit_log=audit_log,
        journal=journal, terminal_meta=terminal_meta, sales_queue=sales_queue, sync_service=sync_service,
        worker=worker, status_service=status_service,
    )
