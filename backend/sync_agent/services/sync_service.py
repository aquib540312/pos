from __future__ import annotations

from dataclasses import dataclass

from sync_agent.config import SyncAgentConfig
from sync_agent.domain.entities import (
    ConflictRecord,
    LocalCustomer,
    LocalProduct,
    LocalStockItem,
    OfflineSale,
)
from sync_agent.domain.repositories import (
    AuditLogRepository,
    ConflictLocalRepository,
    CursorRepository,
    CustomerLocalRepository,
    OfflineSaleQueueRepository,
    ProductLocalRepository,
    StockLocalRepository,
    SyncJournalRepository,
)
from sync_agent.domain.transport import SyncTransport


@dataclass
class PushSummary:
    pushed: int = 0
    applied: int = 0
    conflicts: int = 0
    rejected: int = 0


@dataclass
class PullSummary:
    entity_type: str
    changes_applied: int
    cursor: int
    has_more: bool


class SyncService:
    """Push and pull are independent operations -- either can be run on
    its own (see `push_pending`/`pull_entity_type`), and the background
    worker below decides how to sequence and repeat them. Neither method
    holds a lock across the network call: SQLite writes only happen
    before or after the HTTP round trip, never during it, so a slow or
    hanging request never blocks the local database for other threads.
    """

    def __init__(
        self,
        transport: SyncTransport,
        config: SyncAgentConfig,
        offline_sales: OfflineSaleQueueRepository,
        products: ProductLocalRepository,
        customers: CustomerLocalRepository,
        stock: StockLocalRepository,
        cursors: CursorRepository,
        conflicts: ConflictLocalRepository,
        audit_log: AuditLogRepository,
        journal: SyncJournalRepository,
    ):
        self.transport = transport
        self.config = config
        self.offline_sales = offline_sales
        self.products = products
        self.customers = customers
        self.stock = stock
        self.cursors = cursors
        self.conflicts = conflicts
        self.audit_log = audit_log
        self.journal = journal

    # -- Push --------------------------------------------------------------

    def push_pending(self) -> PushSummary:
        pending = self.offline_sales.list_pending(self.config.push_batch_size)
        if not pending:
            return PushSummary()

        journal_entry = self.journal.begin_cycle("push")
        try:
            payloads = [_sale_to_payload(sale) for sale in pending]
            results = self.transport.push(payloads)
        except Exception:
            self.journal.end_cycle(journal_entry.id, success=False)
            raise

        summary = PushSummary(pushed=len(pending))
        for result in results:
            self._apply_push_result(result, summary)
        self.audit_log.append(
            "sync.push",
            {"pushed": summary.pushed, "applied": summary.applied, "conflicts": summary.conflicts,
             "rejected": summary.rejected},
        )
        self.journal.end_cycle(journal_entry.id, success=True)
        return summary

    def _apply_push_result(self, result: dict, summary: PushSummary) -> None:
        status = result["status"]
        self.offline_sales.update_result(
            result["client_operation_id"], status, result.get("invoice_id"), result.get("conflict_id"),
            result.get("error_detail"),
        )
        if status == "applied":
            summary.applied += 1
        elif status == "conflict":
            summary.conflicts += 1
            if result.get("conflict_id"):
                self.conflicts.upsert(
                    ConflictRecord(
                        id=result["conflict_id"],
                        client_operation_id=result["client_operation_id"],
                        conflict_type=result.get("conflict_type") or "unknown",
                        details={"error_detail": result.get("error_detail")},
                        status="open",
                    )
                )
        elif status == "rejected":
            summary.rejected += 1

    # -- Pull ----------------------------------------------------------------

    def pull_entity_type(self, entity_type: str) -> PullSummary:
        """One entity type's cursor advances only from rows of that same
        type -- this is why pull is done per entity type rather than one
        combined call: a partial sync that only asks for "product" this
        cycle must never move the "customer"/"stock_item" cursors past
        changes it never actually fetched, or those changes would be
        silently skipped forever the next time a full sync runs."""
        cursor = self.cursors.get_cursor(entity_type)
        journal_entry = self.journal.begin_cycle(f"pull:{entity_type}")
        try:
            page = self.transport.pull(cursor, [entity_type], self.config.pull_page_size)
        except Exception:
            self.journal.end_cycle(journal_entry.id, success=False)
            raise

        for change in page["changes"]:
            self._apply_change(change)
        new_cursor = page["next_cursor"]
        self.cursors.set_cursor(entity_type, new_cursor)
        self.journal.end_cycle(journal_entry.id, success=True)

        self.audit_log.append(
            "sync.pull", {"entity_type": entity_type, "changes": len(page["changes"]), "cursor": new_cursor}
        )
        return PullSummary(
            entity_type=entity_type, changes_applied=len(page["changes"]), cursor=new_cursor,
            has_more=page["has_more"],
        )

    def pull_all(self, entity_types: list[str] | None = None) -> list[PullSummary]:
        """Runs each enabled entity type's pull to exhaustion (following
        has_more) before moving to the next -- this is what "partial
        sync" means in practice: pass a subset of entity_types to catch
        up on just those, leaving the rest to a later cycle."""
        types = entity_types if entity_types is not None else list(self.config.enabled_entity_types)
        summaries: list[PullSummary] = []
        for entity_type in types:
            while True:
                summary = self.pull_entity_type(entity_type)
                summaries.append(summary)
                if not summary.has_more:
                    break
        return summaries

    def _apply_change(self, change: dict) -> None:
        entity_type = change["entity_type"]
        operation = change["operation"]
        payload = change["payload"]

        if operation == "delete":
            if entity_type == "product":
                self.products.delete(change["entity_id"])
            elif entity_type == "customer":
                self.customers.delete(change["entity_id"])
            elif entity_type == "stock_item":
                self.stock.delete(change["entity_id"])
            return

        if entity_type == "product":
            self.products.upsert(_product_from_payload(payload))
        elif entity_type == "customer":
            self.customers.upsert(_customer_from_payload(payload))
        elif entity_type == "stock_item":
            self.stock.upsert(_stock_from_payload(payload))


def _sale_to_payload(sale: OfflineSale) -> dict:
    return {
        "client_operation_id": sale.client_operation_id,
        "occurred_at": sale.occurred_at,
        "branch_id": sale.branch_id,
        "warehouse_id": sale.warehouse_id,
        "customer_id": sale.customer_id,
        "items": [
            {
                "product_id": item.product_id, "quantity": item.quantity, "unit_price": item.unit_price,
                "discount_amount": item.discount_amount,
            }
            for item in sale.items
        ],
        "payments": [
            {"method": p.method, "amount": p.amount, "reference": p.reference} for p in sale.payments
        ],
        "is_credit_sale": sale.is_credit_sale,
        "coupon_code": sale.coupon_code,
    }


def _product_from_payload(payload: dict) -> LocalProduct:
    return LocalProduct(
        id=payload["id"], sku=payload["sku"], barcode=payload.get("barcode"), name=payload["name"],
        description=payload.get("description"), category_id=payload.get("category_id"),
        hsn_code_id=payload.get("hsn_code_id"), uom_id=payload.get("uom_id"), mrp=float(payload["mrp"]),
        sale_price=float(payload["sale_price"]), purchase_price=float(payload["purchase_price"]),
        tracks_batches=bool(payload["tracks_batches"]), tracks_serials=bool(payload["tracks_serials"]),
        tracks_expiry=bool(payload["tracks_expiry"]), reorder_level=float(payload["reorder_level"]),
        is_combo=bool(payload["is_combo"]), is_active=bool(payload["is_active"]),
    )


def _customer_from_payload(payload: dict) -> LocalCustomer:
    return LocalCustomer(
        id=payload["id"], name=payload["name"], phone=payload.get("phone"), email=payload.get("email"),
        gstin=payload.get("gstin"), state_code=payload.get("state_code"), address=payload.get("address"),
        is_credit_customer=bool(payload["is_credit_customer"]), credit_limit=float(payload["credit_limit"]),
        credit_balance=float(payload["credit_balance"]),
        loyalty_points_balance=float(payload["loyalty_points_balance"]), is_active=bool(payload["is_active"]),
    )


def _stock_from_payload(payload: dict) -> LocalStockItem:
    return LocalStockItem(
        id=payload["id"], warehouse_id=payload["warehouse_id"], product_id=payload["product_id"],
        batch_id=payload.get("batch_id"), quantity_on_hand=float(payload["quantity_on_hand"]),
    )
