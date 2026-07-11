from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LocalProduct:
    id: str
    sku: str
    barcode: str | None
    name: str
    description: str | None
    category_id: str | None
    hsn_code_id: str | None
    uom_id: str | None
    mrp: float
    sale_price: float
    purchase_price: float
    tracks_batches: bool
    tracks_serials: bool
    tracks_expiry: bool
    reorder_level: float
    is_combo: bool
    is_active: bool


@dataclass
class LocalCustomer:
    id: str
    name: str
    phone: str | None
    email: str | None
    gstin: str | None
    state_code: str | None
    address: str | None
    is_credit_customer: bool
    credit_limit: float
    credit_balance: float
    loyalty_points_balance: float
    is_active: bool


@dataclass
class LocalStockItem:
    id: str
    warehouse_id: str
    product_id: str
    batch_id: str | None
    quantity_on_hand: float


@dataclass
class OfflineSaleLine:
    product_id: str
    quantity: float
    unit_price: float | None = None
    discount_amount: float = 0.0


@dataclass
class OfflineSalePayment:
    method: str
    amount: float
    reference: str | None = None


@dataclass
class OfflineSale:
    """A sale rung up locally while offline. `client_operation_id` is the
    idempotency key the server dedupes on -- generated once, at creation,
    and never regenerated on retry."""

    client_operation_id: str
    occurred_at: str  # ISO 8601, UTC
    branch_id: str
    warehouse_id: str
    items: list[OfflineSaleLine]
    payments: list[OfflineSalePayment] = field(default_factory=list)
    customer_id: str | None = None
    is_credit_sale: bool = False
    coupon_code: str | None = None
    status: str = "pending"  # pending|applied|conflict|rejected
    server_invoice_id: str | None = None
    server_conflict_id: str | None = None
    error_detail: str | None = None


@dataclass
class ConflictRecord:
    id: str
    client_operation_id: str
    conflict_type: str
    details: dict
    status: str = "open"


@dataclass
class AuditEntry:
    id: int | None
    timestamp: str
    action: str
    detail: dict


@dataclass
class SyncJournalEntry:
    """Crash-recovery bookkeeping: a row with `finished_at is None` after
    process restart means the previous run died mid-cycle."""

    id: str
    cycle_type: str  # "push" | "pull"
    started_at: str
    finished_at: str | None = None
    success: bool | None = None
