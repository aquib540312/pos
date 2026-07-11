from __future__ import annotations

from dataclasses import dataclass, field

from sync_agent.domain.repositories import (
    AuditLogRepository,
    ConflictLocalRepository,
    CustomerLocalRepository,
    OfflineSaleQueueRepository,
    ProductLocalRepository,
    StockLocalRepository,
)
from sync_agent.services.background_worker import WorkerState


@dataclass
class SyncStatusSnapshot:
    """Everything a "sync status dashboard" screen needs, assembled
    purely from the local database plus the in-memory worker state --
    this never makes a network call itself, so it renders instantly even
    while offline (which is exactly when a cashier most wants to see it)."""

    worker_running: bool
    last_cycle_at: float | None
    last_success_at: float | None
    last_error: str | None
    consecutive_failures: int
    current_backoff_seconds: float
    needs_reauth: bool
    offline_sales_by_status: dict[str, int]
    open_conflicts: int
    cached_products: int
    cached_customers: int
    cached_stock_rows: int
    recent_audit_actions: list[dict] = field(default_factory=list)


class StatusService:
    def __init__(
        self,
        worker_state: WorkerState,
        offline_sales: OfflineSaleQueueRepository,
        conflicts: ConflictLocalRepository,
        products: ProductLocalRepository,
        customers: CustomerLocalRepository,
        stock: StockLocalRepository,
        audit_log: AuditLogRepository,
    ):
        self.worker_state = worker_state
        self.offline_sales = offline_sales
        self.conflicts = conflicts
        self.products = products
        self.customers = customers
        self.stock = stock
        self.audit_log = audit_log

    def snapshot(self, recent_audit_limit: int = 20) -> SyncStatusSnapshot:
        return SyncStatusSnapshot(
            worker_running=self.worker_state.running,
            last_cycle_at=self.worker_state.last_cycle_at,
            last_success_at=self.worker_state.last_success_at,
            last_error=self.worker_state.last_error,
            consecutive_failures=self.worker_state.consecutive_failures,
            current_backoff_seconds=self.worker_state.current_backoff_seconds,
            needs_reauth=self.worker_state.needs_reauth,
            offline_sales_by_status=self.offline_sales.count_by_status(),
            open_conflicts=len(self.conflicts.list_open()),
            cached_products=self.products.count(),
            cached_customers=self.customers.count(),
            cached_stock_rows=self.stock.count(),
            recent_audit_actions=[
                {"timestamp": e.timestamp, "action": e.action, "detail": e.detail}
                for e in self.audit_log.list_recent(recent_audit_limit)
            ],
        )
