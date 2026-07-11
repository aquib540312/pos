from __future__ import annotations

import pytest

from sync_agent.infrastructure.sqlite_repositories import SqliteAuditLogRepository, SqliteOfflineSaleRepository
from sync_agent.services.offline_sales_queue import OfflineSalesQueueService, ValidationError


def _service(local_db):
    return OfflineSalesQueueService(SqliteOfflineSaleRepository(local_db), SqliteAuditLogRepository(local_db))


def test_enqueue_sale_succeeds_and_is_immediately_pending(local_db):
    service = _service(local_db)
    sale = service.enqueue_sale(
        branch_id="b1", warehouse_id="w1", items=[{"product_id": "p1", "quantity": 2}],
        payments=[{"method": "cash", "amount": 100}],
    )
    assert sale.status == "pending"
    pending = SqliteOfflineSaleRepository(local_db).list_pending(10)
    assert len(pending) == 1
    assert pending[0].client_operation_id == sale.client_operation_id


def test_enqueue_sale_never_rejects_for_stock_reasons():
    """The whole point of offline mode: the queue must never second-guess
    a sale against locally-cached stock, since that cache can be stale.
    There is deliberately no stock check anywhere in this service."""
    import inspect

    from sync_agent.services import offline_sales_queue

    source = inspect.getsource(offline_sales_queue)
    assert "quantity_on_hand" not in source
    assert "StockLocalRepository" not in source


def test_enqueue_sale_rejects_empty_items(local_db):
    service = _service(local_db)
    with pytest.raises(ValidationError):
        service.enqueue_sale(branch_id="b1", warehouse_id="w1", items=[], payments=[])


def test_enqueue_sale_rejects_non_positive_quantity(local_db):
    service = _service(local_db)
    with pytest.raises(ValidationError):
        service.enqueue_sale(
            branch_id="b1", warehouse_id="w1", items=[{"product_id": "p1", "quantity": 0}], payments=[]
        )


def test_enqueue_sale_rejects_missing_branch_or_warehouse(local_db):
    service = _service(local_db)
    with pytest.raises(ValidationError):
        service.enqueue_sale(
            branch_id="", warehouse_id="w1", items=[{"product_id": "p1", "quantity": 1}], payments=[]
        )


def test_each_enqueued_sale_gets_a_unique_idempotency_key(local_db):
    service = _service(local_db)
    sale1 = service.enqueue_sale(
        branch_id="b1", warehouse_id="w1", items=[{"product_id": "p1", "quantity": 1}], payments=[]
    )
    sale2 = service.enqueue_sale(
        branch_id="b1", warehouse_id="w1", items=[{"product_id": "p1", "quantity": 1}], payments=[]
    )
    assert sale1.client_operation_id != sale2.client_operation_id
