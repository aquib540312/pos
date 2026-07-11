from __future__ import annotations

from sync_agent.domain.entities import ConflictRecord, LocalProduct
from sync_agent.infrastructure.sqlite_repositories import (
    SqliteAuditLogRepository,
    SqliteConflictRepository,
    SqliteCustomerRepository,
    SqliteOfflineSaleRepository,
    SqliteProductRepository,
    SqliteStockRepository,
)
from sync_agent.services.background_worker import WorkerState
from sync_agent.services.offline_sales_queue import OfflineSalesQueueService
from sync_agent.services.status import StatusService


def test_status_snapshot_reflects_local_state(local_db):
    products = SqliteProductRepository(local_db)
    customers = SqliteCustomerRepository(local_db)
    stock = SqliteStockRepository(local_db)
    offline_sales = SqliteOfflineSaleRepository(local_db)
    conflicts = SqliteConflictRepository(local_db)
    audit_log = SqliteAuditLogRepository(local_db)

    products.upsert(
        LocalProduct(
            id="p1", sku="SKU1", barcode=None, name="Widget", description=None, category_id=None,
            hsn_code_id=None, uom_id=None, mrp=10, sale_price=9, purchase_price=7, tracks_batches=False,
            tracks_serials=False, tracks_expiry=False, reorder_level=0, is_combo=False, is_active=True,
        )
    )
    conflicts.upsert(
        ConflictRecord(id="conf-1", client_operation_id="op-1", conflict_type="insufficient_stock", details={},
                        status="open")
    )
    queue = OfflineSalesQueueService(offline_sales, audit_log)
    queue.enqueue_sale(branch_id="b1", warehouse_id="w1", items=[{"product_id": "p1", "quantity": 1}], payments=[])

    worker_state = WorkerState(running=True, last_success_at=123.0, consecutive_failures=2)
    status = StatusService(worker_state, offline_sales, conflicts, products, customers, stock, audit_log)
    snapshot = status.snapshot()

    assert snapshot.worker_running is True
    assert snapshot.consecutive_failures == 2
    assert snapshot.open_conflicts == 1
    assert snapshot.cached_products == 1
    assert snapshot.offline_sales_by_status == {"pending": 1}
    assert any(a["action"] == "offline_sale.queued" for a in snapshot.recent_audit_actions)
