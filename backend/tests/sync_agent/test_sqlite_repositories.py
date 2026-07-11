from __future__ import annotations

from sync_agent.domain.entities import (
    ConflictRecord,
    LocalCustomer,
    LocalProduct,
    LocalStockItem,
    OfflineSale,
    OfflineSaleLine,
    OfflineSalePayment,
)
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


def _product(id="p1", **overrides):
    defaults = dict(
        id=id, sku="SKU1", barcode="123", name="Widget", description=None, category_id=None, hsn_code_id=None,
        uom_id=None, mrp=10.0, sale_price=9.0, purchase_price=7.0, tracks_batches=False, tracks_serials=False,
        tracks_expiry=False, reorder_level=5.0, is_combo=False, is_active=True,
    )
    defaults.update(overrides)
    return LocalProduct(**defaults)


def test_product_repository_upsert_and_get(local_db):
    repo = SqliteProductRepository(local_db)
    repo.upsert(_product())
    fetched = repo.get("p1")
    assert fetched.sku == "SKU1"
    assert fetched.is_active is True
    assert repo.count() == 1

    repo.upsert(_product(sale_price=8.5, is_active=False))
    updated = repo.get("p1")
    assert updated.sale_price == 8.5
    assert updated.is_active is False
    assert repo.count() == 1  # upsert, not a second row


def test_product_repository_delete(local_db):
    repo = SqliteProductRepository(local_db)
    repo.upsert(_product())
    repo.delete("p1")
    assert repo.get("p1") is None
    assert repo.count() == 0


def test_customer_repository_roundtrip(local_db):
    repo = SqliteCustomerRepository(local_db)
    customer = LocalCustomer(
        id="c1", name="Jane", phone="9998887777", email=None, gstin=None, state_code="27", address=None,
        is_credit_customer=True, credit_limit=1000, credit_balance=250, loyalty_points_balance=12.5,
        is_active=True,
    )
    repo.upsert(customer)
    fetched = repo.get("c1")
    assert fetched.name == "Jane"
    assert fetched.is_credit_customer is True
    assert fetched.credit_balance == 250

    repo.delete("c1")
    assert repo.get("c1") is None


def test_stock_repository_quantity_on_hand_sums_across_batches(local_db):
    repo = SqliteStockRepository(local_db)
    repo.upsert(LocalStockItem(id="s1", warehouse_id="w1", product_id="p1", batch_id="b1", quantity_on_hand=10))
    repo.upsert(LocalStockItem(id="s2", warehouse_id="w1", product_id="p1", batch_id="b2", quantity_on_hand=5))
    repo.upsert(LocalStockItem(id="s3", warehouse_id="w2", product_id="p1", batch_id="b1", quantity_on_hand=100))
    assert repo.quantity_on_hand("w1", "p1") == 15
    assert repo.quantity_on_hand("w2", "p1") == 100
    assert repo.count() == 3


def _offline_sale(op_id="op-1"):
    return OfflineSale(
        client_operation_id=op_id, occurred_at="2026-01-01T00:00:00+00:00", branch_id="b1", warehouse_id="w1",
        items=[OfflineSaleLine(product_id="p1", quantity=2)],
        payments=[OfflineSalePayment(method="cash", amount=100)],
    )


def test_offline_sale_repository_enqueue_and_list_pending(local_db):
    repo = SqliteOfflineSaleRepository(local_db)
    repo.enqueue(_offline_sale("op-1"))
    repo.enqueue(_offline_sale("op-2"))

    pending = repo.list_pending(10)
    assert {s.client_operation_id for s in pending} == {"op-1", "op-2"}
    assert repo.count_pending() == 2

    fetched = repo.get("op-1")
    assert fetched.items[0].product_id == "p1"
    assert fetched.payments[0].amount == 100


def test_offline_sale_repository_update_result_removes_from_pending(local_db):
    repo = SqliteOfflineSaleRepository(local_db)
    repo.enqueue(_offline_sale("op-1"))
    repo.update_result("op-1", "applied", "inv-1", None, None)

    assert repo.count_pending() == 0
    sale = repo.get("op-1")
    assert sale.status == "applied"
    assert sale.server_invoice_id == "inv-1"
    assert repo.count_by_status() == {"applied": 1}


def test_cursor_repository_defaults_to_zero_then_persists(local_db):
    repo = SqliteCursorRepository(local_db)
    assert repo.get_cursor("product") == 0
    repo.set_cursor("product", 42)
    assert repo.get_cursor("product") == 42
    repo.set_cursor("product", 99)
    assert repo.get_cursor("product") == 99
    assert repo.get_cursor("customer") == 0  # independent cursor per entity type


def test_conflict_repository_list_open_excludes_resolved(local_db):
    repo = SqliteConflictRepository(local_db)
    repo.upsert(ConflictRecord(id="conf-1", client_operation_id="op-1", conflict_type="insufficient_stock",
                                details={}, status="open"))
    repo.upsert(ConflictRecord(id="conf-2", client_operation_id="op-2", conflict_type="insufficient_stock",
                                details={}, status="resolved"))
    open_conflicts = repo.list_open()
    assert len(open_conflicts) == 1
    assert open_conflicts[0].id == "conf-1"


def test_audit_log_repository_append_and_list_recent_orders_newest_first(local_db):
    repo = SqliteAuditLogRepository(local_db)
    repo.append("action.one", {"n": 1})
    repo.append("action.two", {"n": 2})
    recent = repo.list_recent(10)
    assert [e.action for e in recent] == ["action.two", "action.one"]
    assert recent[0].detail == {"n": 2}


def test_sync_journal_repository_tracks_incomplete_cycles(local_db):
    repo = SqliteSyncJournalRepository(local_db)
    entry = repo.begin_cycle("push")
    incomplete = repo.find_incomplete_cycles()
    assert len(incomplete) == 1
    assert incomplete[0].id == entry.id
    assert incomplete[0].finished_at is None

    repo.end_cycle(entry.id, success=True)
    assert repo.find_incomplete_cycles() == []


def test_terminal_meta_repository_set_and_get(local_db):
    repo = SqliteTerminalMetaRepository(local_db)
    assert repo.get("api_key") is None
    repo.set("api_key", "abc123")
    assert repo.get("api_key") == "abc123"
    repo.set("api_key", "def456")
    assert repo.get("api_key") == "def456"
