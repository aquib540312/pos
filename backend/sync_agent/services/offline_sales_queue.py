from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sync_agent.domain.entities import OfflineSale, OfflineSaleLine, OfflineSalePayment
from sync_agent.domain.repositories import AuditLogRepository, OfflineSaleQueueRepository


class ValidationError(Exception):
    pass


class OfflineSalesQueueService:
    """The till's write path while offline: every sale rung up gets a
    locally-generated idempotency key and lands in the queue immediately,
    unconditionally -- it is never rejected here for "insufficient stock"
    against the local cache, because that cache is a snapshot from the
    last successful pull and may already be stale (that's the whole
    reason the server does the authoritative, oversell-safe check at sync
    time and raises a conflict if it turns out to be wrong). Blocking a
    sale locally on a number that might be wrong would defeat the point
    of working offline at all.
    """

    def __init__(self, queue: OfflineSaleQueueRepository, audit_log: AuditLogRepository):
        self.queue = queue
        self.audit_log = audit_log

    def enqueue_sale(
        self,
        branch_id: str,
        warehouse_id: str,
        items: list[dict],
        payments: list[dict],
        customer_id: str | None = None,
        is_credit_sale: bool = False,
        coupon_code: str | None = None,
    ) -> OfflineSale:
        if not branch_id or not warehouse_id:
            raise ValidationError("branch_id and warehouse_id are required")
        if not items:
            raise ValidationError("A sale needs at least one line item")
        for item in items:
            if not item.get("product_id"):
                raise ValidationError("Every line item needs a product_id")
            if not isinstance(item.get("quantity"), (int, float)) or item["quantity"] <= 0:
                raise ValidationError(f"Line item quantity must be positive, got {item.get('quantity')!r}")
        for payment in payments:
            if not isinstance(payment.get("amount"), (int, float)) or payment["amount"] <= 0:
                raise ValidationError(f"Payment amount must be positive, got {payment.get('amount')!r}")

        sale = OfflineSale(
            client_operation_id=str(uuid.uuid4()),
            occurred_at=datetime.now(timezone.utc).isoformat(),
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            customer_id=customer_id,
            items=[OfflineSaleLine(**item) for item in items],
            payments=[OfflineSalePayment(**payment) for payment in payments],
            is_credit_sale=is_credit_sale,
            coupon_code=coupon_code,
        )
        self.queue.enqueue(sale)
        self.audit_log.append(
            "offline_sale.queued",
            {"client_operation_id": sale.client_operation_id, "item_count": len(items)},
        )
        return sale
