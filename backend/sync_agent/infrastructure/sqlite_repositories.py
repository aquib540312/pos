from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sync_agent.domain.entities import (
    AuditEntry,
    ConflictRecord,
    LocalCustomer,
    LocalProduct,
    LocalStockItem,
    OfflineSale,
    OfflineSaleLine,
    OfflineSalePayment,
    SyncJournalEntry,
)
from sync_agent.infrastructure.db import LocalDatabase


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bool(value) -> bool:
    return bool(value)


class SqliteProductRepository:
    def __init__(self, db: LocalDatabase):
        self.db = db

    def upsert(self, product: LocalProduct) -> None:
        with self.db.lock:
            self.db.cursor().execute(
                """
                INSERT INTO products (
                    id, sku, barcode, name, description, category_id, hsn_code_id, uom_id, mrp, sale_price,
                    purchase_price, tracks_batches, tracks_serials, tracks_expiry, reorder_level, is_combo, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    sku=excluded.sku, barcode=excluded.barcode, name=excluded.name,
                    description=excluded.description, category_id=excluded.category_id,
                    hsn_code_id=excluded.hsn_code_id, uom_id=excluded.uom_id, mrp=excluded.mrp,
                    sale_price=excluded.sale_price, purchase_price=excluded.purchase_price,
                    tracks_batches=excluded.tracks_batches, tracks_serials=excluded.tracks_serials,
                    tracks_expiry=excluded.tracks_expiry, reorder_level=excluded.reorder_level,
                    is_combo=excluded.is_combo, is_active=excluded.is_active
                """,
                (
                    product.id, product.sku, product.barcode, product.name, product.description,
                    product.category_id, product.hsn_code_id, product.uom_id, product.mrp, product.sale_price,
                    product.purchase_price, int(product.tracks_batches), int(product.tracks_serials),
                    int(product.tracks_expiry), product.reorder_level, int(product.is_combo), int(product.is_active),
                ),
            )
            self.db.commit()

    def delete(self, product_id: str) -> None:
        with self.db.lock:
            self.db.cursor().execute("DELETE FROM products WHERE id = ?", (product_id,))
            self.db.commit()

    def get(self, product_id: str) -> LocalProduct | None:
        row = self.db.cursor().execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
        return _row_to_product(row) if row else None

    def list_all(self) -> list[LocalProduct]:
        rows = self.db.cursor().execute("SELECT * FROM products ORDER BY name").fetchall()
        return [_row_to_product(r) for r in rows]

    def count(self) -> int:
        return self.db.cursor().execute("SELECT COUNT(*) FROM products").fetchone()[0]


def _row_to_product(row) -> LocalProduct:
    return LocalProduct(
        id=row["id"], sku=row["sku"], barcode=row["barcode"], name=row["name"], description=row["description"],
        category_id=row["category_id"], hsn_code_id=row["hsn_code_id"], uom_id=row["uom_id"], mrp=row["mrp"],
        sale_price=row["sale_price"], purchase_price=row["purchase_price"],
        tracks_batches=_bool(row["tracks_batches"]), tracks_serials=_bool(row["tracks_serials"]),
        tracks_expiry=_bool(row["tracks_expiry"]), reorder_level=row["reorder_level"],
        is_combo=_bool(row["is_combo"]), is_active=_bool(row["is_active"]),
    )


class SqliteCustomerRepository:
    def __init__(self, db: LocalDatabase):
        self.db = db

    def upsert(self, customer: LocalCustomer) -> None:
        with self.db.lock:
            self.db.cursor().execute(
                """
                INSERT INTO customers (
                    id, name, phone, email, gstin, state_code, address, is_credit_customer, credit_limit,
                    credit_balance, loyalty_points_balance, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, phone=excluded.phone, email=excluded.email, gstin=excluded.gstin,
                    state_code=excluded.state_code, address=excluded.address,
                    is_credit_customer=excluded.is_credit_customer, credit_limit=excluded.credit_limit,
                    credit_balance=excluded.credit_balance, loyalty_points_balance=excluded.loyalty_points_balance,
                    is_active=excluded.is_active
                """,
                (
                    customer.id, customer.name, customer.phone, customer.email, customer.gstin,
                    customer.state_code, customer.address, int(customer.is_credit_customer), customer.credit_limit,
                    customer.credit_balance, customer.loyalty_points_balance, int(customer.is_active),
                ),
            )
            self.db.commit()

    def delete(self, customer_id: str) -> None:
        with self.db.lock:
            self.db.cursor().execute("DELETE FROM customers WHERE id = ?", (customer_id,))
            self.db.commit()

    def get(self, customer_id: str) -> LocalCustomer | None:
        row = self.db.cursor().execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
        return _row_to_customer(row) if row else None

    def list_all(self) -> list[LocalCustomer]:
        rows = self.db.cursor().execute("SELECT * FROM customers ORDER BY name").fetchall()
        return [_row_to_customer(r) for r in rows]

    def count(self) -> int:
        return self.db.cursor().execute("SELECT COUNT(*) FROM customers").fetchone()[0]


def _row_to_customer(row) -> LocalCustomer:
    return LocalCustomer(
        id=row["id"], name=row["name"], phone=row["phone"], email=row["email"], gstin=row["gstin"],
        state_code=row["state_code"], address=row["address"], is_credit_customer=_bool(row["is_credit_customer"]),
        credit_limit=row["credit_limit"], credit_balance=row["credit_balance"],
        loyalty_points_balance=row["loyalty_points_balance"], is_active=_bool(row["is_active"]),
    )


class SqliteStockRepository:
    def __init__(self, db: LocalDatabase):
        self.db = db

    def upsert(self, stock: LocalStockItem) -> None:
        with self.db.lock:
            self.db.cursor().execute(
                """
                INSERT INTO stock_items (id, warehouse_id, product_id, batch_id, quantity_on_hand)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    warehouse_id=excluded.warehouse_id, product_id=excluded.product_id,
                    batch_id=excluded.batch_id, quantity_on_hand=excluded.quantity_on_hand
                """,
                (stock.id, stock.warehouse_id, stock.product_id, stock.batch_id, stock.quantity_on_hand),
            )
            self.db.commit()

    def delete(self, stock_id: str) -> None:
        with self.db.lock:
            self.db.cursor().execute("DELETE FROM stock_items WHERE id = ?", (stock_id,))
            self.db.commit()

    def get(self, stock_id: str) -> LocalStockItem | None:
        row = self.db.cursor().execute("SELECT * FROM stock_items WHERE id = ?", (stock_id,)).fetchone()
        return _row_to_stock(row) if row else None

    def quantity_on_hand(self, warehouse_id: str, product_id: str) -> float:
        row = self.db.cursor().execute(
            "SELECT COALESCE(SUM(quantity_on_hand), 0) FROM stock_items WHERE warehouse_id = ? AND product_id = ?",
            (warehouse_id, product_id),
        ).fetchone()
        return float(row[0])

    def count(self) -> int:
        return self.db.cursor().execute("SELECT COUNT(*) FROM stock_items").fetchone()[0]


def _row_to_stock(row) -> LocalStockItem:
    return LocalStockItem(
        id=row["id"], warehouse_id=row["warehouse_id"], product_id=row["product_id"], batch_id=row["batch_id"],
        quantity_on_hand=row["quantity_on_hand"],
    )


class SqliteOfflineSaleRepository:
    def __init__(self, db: LocalDatabase):
        self.db = db

    def enqueue(self, sale: OfflineSale) -> None:
        with self.db.lock:
            self.db.cursor().execute(
                """
                INSERT INTO offline_sales (
                    client_operation_id, occurred_at, branch_id, warehouse_id, customer_id, items_json,
                    payments_json, is_credit_sale, coupon_code, status, server_invoice_id, server_conflict_id,
                    error_detail, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sale.client_operation_id, sale.occurred_at, sale.branch_id, sale.warehouse_id,
                    sale.customer_id, json.dumps([_line_to_dict(item) for item in sale.items]),
                    json.dumps([_payment_to_dict(p) for p in sale.payments]), int(sale.is_credit_sale),
                    sale.coupon_code, sale.status, sale.server_invoice_id, sale.server_conflict_id,
                    sale.error_detail, _now_iso(),
                ),
            )
            self.db.commit()

    def get(self, client_operation_id: str) -> OfflineSale | None:
        row = self.db.cursor().execute(
            "SELECT * FROM offline_sales WHERE client_operation_id = ?", (client_operation_id,)
        ).fetchone()
        return _row_to_sale(row) if row else None

    def list_pending(self, limit: int) -> list[OfflineSale]:
        rows = self.db.cursor().execute(
            "SELECT * FROM offline_sales WHERE status = 'pending' ORDER BY created_at LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_sale(r) for r in rows]

    def update_result(
        self,
        client_operation_id: str,
        status: str,
        invoice_id: str | None,
        conflict_id: str | None,
        error_detail: str | None,
    ) -> None:
        with self.db.lock:
            self.db.cursor().execute(
                """
                UPDATE offline_sales
                SET status = ?, server_invoice_id = ?, server_conflict_id = ?, error_detail = ?
                WHERE client_operation_id = ?
                """,
                (status, invoice_id, conflict_id, error_detail, client_operation_id),
            )
            self.db.commit()

    def count_pending(self) -> int:
        return self.db.cursor().execute("SELECT COUNT(*) FROM offline_sales WHERE status = 'pending'").fetchone()[0]

    def count_by_status(self) -> dict[str, int]:
        rows = self.db.cursor().execute("SELECT status, COUNT(*) FROM offline_sales GROUP BY status").fetchall()
        return {r[0]: r[1] for r in rows}


def _line_to_dict(item: OfflineSaleLine) -> dict:
    return {
        "product_id": item.product_id, "quantity": item.quantity, "unit_price": item.unit_price,
        "discount_amount": item.discount_amount,
    }


def _payment_to_dict(payment: OfflineSalePayment) -> dict:
    return {"method": payment.method, "amount": payment.amount, "reference": payment.reference}


def _row_to_sale(row) -> OfflineSale:
    items = [OfflineSaleLine(**d) for d in json.loads(row["items_json"])]
    payments = [OfflineSalePayment(**d) for d in json.loads(row["payments_json"])]
    return OfflineSale(
        client_operation_id=row["client_operation_id"], occurred_at=row["occurred_at"], branch_id=row["branch_id"],
        warehouse_id=row["warehouse_id"], customer_id=row["customer_id"], items=items, payments=payments,
        is_credit_sale=_bool(row["is_credit_sale"]), coupon_code=row["coupon_code"], status=row["status"],
        server_invoice_id=row["server_invoice_id"], server_conflict_id=row["server_conflict_id"],
        error_detail=row["error_detail"],
    )


class SqliteCursorRepository:
    def __init__(self, db: LocalDatabase):
        self.db = db

    def get_cursor(self, entity_type: str) -> int:
        row = self.db.cursor().execute(
            "SELECT cursor_value FROM sync_cursors WHERE entity_type = ?", (entity_type,)
        ).fetchone()
        return int(row[0]) if row else 0

    def set_cursor(self, entity_type: str, value: int) -> None:
        with self.db.lock:
            self.db.cursor().execute(
                """
                INSERT INTO sync_cursors (entity_type, cursor_value) VALUES (?, ?)
                ON CONFLICT(entity_type) DO UPDATE SET cursor_value = excluded.cursor_value
                """,
                (entity_type, value),
            )
            self.db.commit()


class SqliteConflictRepository:
    def __init__(self, db: LocalDatabase):
        self.db = db

    def upsert(self, conflict: ConflictRecord) -> None:
        with self.db.lock:
            self.db.cursor().execute(
                """
                INSERT INTO conflicts (id, client_operation_id, conflict_type, details_json, status)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    conflict_type=excluded.conflict_type, details_json=excluded.details_json, status=excluded.status
                """,
                (conflict.id, conflict.client_operation_id, conflict.conflict_type, json.dumps(conflict.details),
                 conflict.status),
            )
            self.db.commit()

    def list_open(self) -> list[ConflictRecord]:
        rows = self.db.cursor().execute("SELECT * FROM conflicts WHERE status = 'open'").fetchall()
        return [
            ConflictRecord(
                id=r["id"], client_operation_id=r["client_operation_id"], conflict_type=r["conflict_type"],
                details=json.loads(r["details_json"]), status=r["status"],
            )
            for r in rows
        ]


class SqliteAuditLogRepository:
    def __init__(self, db: LocalDatabase):
        self.db = db

    def append(self, action: str, detail: dict) -> None:
        with self.db.lock:
            self.db.cursor().execute(
                "INSERT INTO audit_log (timestamp, action, detail_json) VALUES (?, ?, ?)",
                (_now_iso(), action, json.dumps(detail, default=str)),
            )
            self.db.commit()

    def list_recent(self, limit: int) -> list[AuditEntry]:
        rows = self.db.cursor().execute(
            "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            AuditEntry(id=r["id"], timestamp=r["timestamp"], action=r["action"], detail=json.loads(r["detail_json"]))
            for r in rows
        ]


class SqliteSyncJournalRepository:
    def __init__(self, db: LocalDatabase):
        self.db = db

    def begin_cycle(self, cycle_type: str) -> SyncJournalEntry:
        entry = SyncJournalEntry(id=str(uuid.uuid4()), cycle_type=cycle_type, started_at=_now_iso())
        with self.db.lock:
            self.db.cursor().execute(
                "INSERT INTO sync_journal (id, cycle_type, started_at) VALUES (?, ?, ?)",
                (entry.id, entry.cycle_type, entry.started_at),
            )
            self.db.commit()
        return entry

    def end_cycle(self, journal_id: str, success: bool) -> None:
        with self.db.lock:
            self.db.cursor().execute(
                "UPDATE sync_journal SET finished_at = ?, success = ? WHERE id = ?",
                (_now_iso(), int(success), journal_id),
            )
            self.db.commit()

    def find_incomplete_cycles(self) -> list[SyncJournalEntry]:
        rows = self.db.cursor().execute("SELECT * FROM sync_journal WHERE finished_at IS NULL").fetchall()
        return [
            SyncJournalEntry(
                id=r["id"], cycle_type=r["cycle_type"], started_at=r["started_at"], finished_at=r["finished_at"],
                success=None if r["success"] is None else bool(r["success"]),
            )
            for r in rows
        ]


class SqliteTerminalMetaRepository:
    """Small persisted key/value store for what `register` learns once --
    terminal_id, api_key, branch_id -- so subsequent runs don't need to
    re-register or be re-configured via environment every time."""

    def __init__(self, db: LocalDatabase):
        self.db = db

    def get(self, key: str) -> str | None:
        row = self.db.cursor().execute("SELECT value FROM terminal_meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set(self, key: str, value: str) -> None:
        with self.db.lock:
            self.db.cursor().execute(
                """
                INSERT INTO terminal_meta (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
            self.db.commit()
