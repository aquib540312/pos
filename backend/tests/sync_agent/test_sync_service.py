from __future__ import annotations

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
from sync_agent.services.offline_sales_queue import OfflineSalesQueueService
from sync_agent.services.sync_service import SyncService
from tests.sync_agent.fakes import FakeTransport


def _make_service(local_db, agent_config, transport=None):
    transport = transport or FakeTransport()
    offline_sales = SqliteOfflineSaleRepository(local_db)
    products = SqliteProductRepository(local_db)
    customers = SqliteCustomerRepository(local_db)
    stock = SqliteStockRepository(local_db)
    cursors = SqliteCursorRepository(local_db)
    conflicts = SqliteConflictRepository(local_db)
    audit_log = SqliteAuditLogRepository(local_db)
    journal = SqliteSyncJournalRepository(local_db)
    service = SyncService(
        transport, agent_config, offline_sales, products, customers, stock, cursors, conflicts, audit_log, journal
    )
    return service, transport, offline_sales, products, customers, stock, cursors, conflicts


def test_push_pending_applies_sales_and_updates_local_status(local_db, agent_config):
    service, transport, offline_sales, *_ = _make_service(local_db, agent_config)
    queue = OfflineSalesQueueService(offline_sales, SqliteAuditLogRepository(local_db))
    sale = queue.enqueue_sale(
        branch_id="b1", warehouse_id="w1", items=[{"product_id": "p1", "quantity": 1}],
        payments=[{"method": "cash", "amount": 47}],
    )

    summary = service.push_pending()

    assert summary.pushed == 1
    assert summary.applied == 1
    assert offline_sales.count_pending() == 0
    updated = offline_sales.get(sale.client_operation_id)
    assert updated.status == "applied"
    assert updated.server_invoice_id == f"inv-{sale.client_operation_id}"


def test_push_pending_with_nothing_queued_is_a_no_op(local_db, agent_config):
    service, transport, *_ = _make_service(local_db, agent_config)
    summary = service.push_pending()
    assert summary.pushed == 0
    assert transport.pushed_batches == []


def test_push_records_conflict_locally_when_server_reports_one(local_db, agent_config):
    service, transport, offline_sales, products, customers, stock, cursors, conflicts = _make_service(
        local_db, agent_config
    )
    queue = OfflineSalesQueueService(offline_sales, SqliteAuditLogRepository(local_db))
    sale = queue.enqueue_sale(
        branch_id="b1", warehouse_id="w1", items=[{"product_id": "p1", "quantity": 5}], payments=[]
    )
    transport.set_result_for(
        sale.client_operation_id,
        {
            "client_operation_id": sale.client_operation_id, "status": "conflict", "invoice_id": None,
            "conflict_id": "conf-1", "conflict_type": "insufficient_stock", "error_detail": "short by 4",
        },
    )

    summary = service.push_pending()

    assert summary.conflicts == 1
    open_conflicts = conflicts.list_open()
    assert len(open_conflicts) == 1
    assert open_conflicts[0].conflict_type == "insufficient_stock"
    updated = offline_sales.get(sale.client_operation_id)
    assert updated.status == "conflict"
    assert updated.error_detail == "short by 4"


def test_pull_entity_type_applies_product_upserts_and_advances_cursor(local_db, agent_config):
    service, transport, offline_sales, products, *_ = _make_service(local_db, agent_config)
    transport.seed_change(
        "product", "create", "p1",
        {
            "id": "p1", "sku": "SKU1", "barcode": None, "name": "Widget", "description": None,
            "category_id": None, "hsn_code_id": None, "uom_id": None, "mrp": 10, "sale_price": 9,
            "purchase_price": 7, "tracks_batches": False, "tracks_serials": False, "tracks_expiry": False,
            "reorder_level": 0, "is_combo": False, "is_active": True,
        },
    )

    summary = service.pull_entity_type("product")

    assert summary.changes_applied == 1
    assert summary.cursor == 1
    assert products.get("p1").name == "Widget"


def test_pull_entity_type_applies_delete(local_db, agent_config):
    service, transport, offline_sales, products, *_ = _make_service(local_db, agent_config)
    transport.seed_change(
        "product", "create", "p1",
        {"id": "p1", "sku": "SKU1", "barcode": None, "name": "Widget", "description": None, "category_id": None,
         "hsn_code_id": None, "uom_id": None, "mrp": 10, "sale_price": 9, "purchase_price": 7,
         "tracks_batches": False, "tracks_serials": False, "tracks_expiry": False, "reorder_level": 0,
         "is_combo": False, "is_active": True},
    )
    service.pull_entity_type("product")
    assert products.get("p1") is not None

    transport.seed_change("product", "delete", "p1", {})
    service.pull_entity_type("product")
    assert products.get("p1") is None


def test_partial_sync_never_skips_other_entity_types_cursor(local_db, agent_config):
    """The critical correctness property: pulling only 'product' this
    cycle must not advance the 'customer' cursor past customer changes
    that were never actually fetched -- otherwise a later full sync would
    silently lose them forever."""
    service, transport, offline_sales, products, customers, stock, cursors, conflicts = _make_service(
        local_db, agent_config
    )
    transport.seed_change(
        "customer", "create", "c1",
        {"id": "c1", "name": "Jane", "phone": None, "email": None, "gstin": None, "state_code": None,
         "address": None, "is_credit_customer": False, "credit_limit": 0, "credit_balance": 0,
         "loyalty_points_balance": 0, "is_active": True},
    )
    transport.seed_change(
        "product", "create", "p1",
        {"id": "p1", "sku": "SKU1", "barcode": None, "name": "Widget", "description": None, "category_id": None,
         "hsn_code_id": None, "uom_id": None, "mrp": 10, "sale_price": 9, "purchase_price": 7,
         "tracks_batches": False, "tracks_serials": False, "tracks_expiry": False, "reorder_level": 0,
         "is_combo": False, "is_active": True},
    )

    # Partial sync: only product this cycle.
    service.pull_entity_type("product")
    assert products.get("p1") is not None
    assert customers.get("c1") is None  # not pulled yet
    assert cursors.get_cursor("product") == 2  # advanced past the product row (id=2)
    assert cursors.get_cursor("customer") == 0  # untouched -- must not skip id=1's customer row

    # A later cycle that does pull customers must still see it.
    service.pull_entity_type("customer")
    assert customers.get("c1") is not None
    assert cursors.get_cursor("customer") == 1


def test_pull_entity_type_paginates_via_has_more(local_db, agent_config):
    service, transport, offline_sales, products, *_ = _make_service(local_db, agent_config)
    transport.pull_page_size_override = 1
    for i in range(3):
        transport.seed_change(
            "product", "create", f"p{i}",
            {"id": f"p{i}", "sku": f"SKU{i}", "barcode": None, "name": f"Widget {i}", "description": None,
             "category_id": None, "hsn_code_id": None, "uom_id": None, "mrp": 10, "sale_price": 9,
             "purchase_price": 7, "tracks_batches": False, "tracks_serials": False, "tracks_expiry": False,
             "reorder_level": 0, "is_combo": False, "is_active": True},
        )

    summaries = service.pull_all(["product"])
    assert len(summaries) == 3  # one call per page since page_size override = 1
    assert products.count() == 3
    assert summaries[-1].has_more is False
