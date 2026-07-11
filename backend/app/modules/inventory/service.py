import uuid

from sqlalchemy.orm import Session

from app.core.exceptions import InsufficientStockError
from app.models.inventory import StockItem
from app.modules.inventory.repository import StockRepository


class InventoryService:
    """The single choke point through which every stock quantity change
    flows -- purchasing (GRN receipt), sales (invoice posting, returns),
    transfers, and manual adjustments all call `receive` / `issue` here
    rather than touching StockItem rows directly, so the ledger and the
    cached balance never drift apart."""

    def __init__(self, db: Session):
        self.db = db
        self.stock = StockRepository(db)

    def receive(
        self,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        batch_id: uuid.UUID | None,
        quantity: float,
        movement_type: str,
        reference_type: str,
        reference_id: uuid.UUID,
        notes: str | None = None,
    ) -> StockItem:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        item = self.stock.get_or_create_stock_item(organization_id, warehouse_id, product_id, batch_id)
        item.quantity_on_hand = float(item.quantity_on_hand) + quantity
        self.stock.write_ledger_entry(
            organization_id, warehouse_id, product_id, batch_id, movement_type, quantity, reference_type,
            reference_id, notes,
        )
        self.db.flush()
        return item

    def issue(
        self,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        batch_id: uuid.UUID | None,
        quantity: float,
        movement_type: str,
        reference_type: str,
        reference_id: uuid.UUID,
        notes: str | None = None,
        allow_negative: bool = False,
    ) -> StockItem:
        if quantity <= 0:
            raise ValueError("quantity must be positive")
        item = self.stock.get_or_create_stock_item(organization_id, warehouse_id, product_id, batch_id)
        if not allow_negative and float(item.quantity_on_hand) < quantity:
            raise InsufficientStockError(
                f"Insufficient stock for product {product_id}: have {item.quantity_on_hand}, need {quantity}"
            )
        item.quantity_on_hand = float(item.quantity_on_hand) - quantity
        self.stock.write_ledger_entry(
            organization_id, warehouse_id, product_id, batch_id, movement_type, -quantity, reference_type,
            reference_id, notes,
        )
        self.db.flush()
        return item

    def issue_fefo(
        self,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        quantity: float,
        movement_type: str,
        reference_type: str,
        reference_id: uuid.UUID,
    ) -> list[tuple[uuid.UUID | None, float]]:
        """Allocate `quantity` across batches First-Expiry-First-Out,
        splitting across multiple batches if one alone doesn't cover the
        request. Returns the (batch_id, quantity) allocations actually
        posted -- the caller (sales service) uses the first allocation as
        the invoice line's `batch_id` for display; every allocation still
        gets its own stock ledger entry so the audit trail is exact even
        when a single sale line draws from more than one batch."""
        remaining = quantity
        allocations: list[tuple[uuid.UUID | None, float]] = []
        for item in self.stock.list_available_batches_fefo(warehouse_id, product_id):
            if remaining <= 0:
                break
            take = min(remaining, float(item.quantity_on_hand))
            if take <= 0:
                continue
            self.issue(
                organization_id, warehouse_id, product_id, item.batch_id, take, movement_type, reference_type,
                reference_id,
            )
            allocations.append((item.batch_id, take))
            remaining -= take

        if remaining > 1e-9:
            raise InsufficientStockError(
                f"Insufficient stock for product {product_id}: short by {remaining} in warehouse {warehouse_id}"
            )
        return allocations

    def stock_on_hand(self, warehouse_id: uuid.UUID, product_id: uuid.UUID) -> float:
        return self.stock.total_quantity(warehouse_id, product_id)

    def list_stock(self, organization_id: uuid.UUID, warehouse_id: uuid.UUID | None = None):
        return self.stock.list_stock(organization_id, warehouse_id)
