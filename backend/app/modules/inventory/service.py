import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, InsufficientStockError, NotFoundError, ValidationError
from app.core.numbering import next_document_number
from app.models.inventory import StockItem, StockTransfer, StockTransferItem
from app.modules.inventory.repository import StockRepository, StockTransferRepository


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


class StockTransferService:
    """Transfers move stock through an explicit draft -> dispatched ->
    received lifecycle rather than an instant move, matching how goods
    actually travel between branches/warehouses: they leave the source
    (and are no longer sellable there) before they arrive and become
    sellable at the destination. The gap between dispatch and receipt is
    real goods-in-transit time, not just bookkeeping."""

    def __init__(self, db: Session):
        self.db = db
        self.transfers = StockTransferRepository(db)
        self.inventory = InventoryService(db)

    def create_transfer(
        self,
        organization_id: uuid.UUID,
        source_warehouse_id: uuid.UUID,
        destination_warehouse_id: uuid.UUID,
        items: list[dict],
    ) -> StockTransfer:
        if source_warehouse_id == destination_warehouse_id:
            raise ValidationError("Source and destination warehouse must differ")

        transfer = StockTransfer(
            organization_id=organization_id,
            transfer_number=next_document_number(self.db, StockTransfer, "TRF"),
            source_warehouse_id=source_warehouse_id,
            destination_warehouse_id=destination_warehouse_id,
            status="draft",
        )
        self.transfers.add(transfer)
        for item in items:
            self.db.add(
                StockTransferItem(
                    transfer_id=transfer.id,
                    product_id=item["product_id"],
                    batch_id=item.get("batch_id"),
                    quantity=item["quantity"],
                )
            )
        self.db.flush()
        return self.transfers.get(transfer.id)

    def dispatch_transfer(self, organization_id: uuid.UUID, transfer_id: uuid.UUID) -> StockTransfer:
        transfer = self.transfers.get(transfer_id)
        if transfer is None:
            raise NotFoundError(f"Stock transfer {transfer_id} not found")
        if transfer.status != "draft":
            raise ConflictError(f"Transfer {transfer.transfer_number} is not in draft status")

        for item in transfer.items:
            if item.batch_id is not None:
                # Caller pinned an exact batch (e.g. transferring a specific
                # expiry-dated lot) -- issue from that batch only.
                self.inventory.issue(
                    organization_id, transfer.source_warehouse_id, item.product_id, item.batch_id,
                    float(item.quantity), "transfer_out", "stock_transfer", transfer.id,
                )
            else:
                # No batch specified: draw First-Expiry-First-Out, same as a
                # sale. Record the first batch consumed on the item so
                # receive_transfer() puts the stock back under the batch it
                # actually came from -- if the line spanned multiple batches,
                # only the primary one is tracked here (see the identical
                # simplification for sales invoice lines in sales/service.py).
                allocations = self.inventory.issue_fefo(
                    organization_id, transfer.source_warehouse_id, item.product_id, float(item.quantity),
                    "transfer_out", "stock_transfer", transfer.id,
                )
                item.batch_id = allocations[0][0] if allocations else None

        transfer.status = "dispatched"
        transfer.dispatched_at = datetime.now(timezone.utc)
        self.db.flush()
        return transfer

    def receive_transfer(self, organization_id: uuid.UUID, transfer_id: uuid.UUID) -> StockTransfer:
        transfer = self.transfers.get(transfer_id)
        if transfer is None:
            raise NotFoundError(f"Stock transfer {transfer_id} not found")
        if transfer.status != "dispatched":
            raise ConflictError(f"Transfer {transfer.transfer_number} has not been dispatched yet")

        for item in transfer.items:
            self.inventory.receive(
                organization_id, transfer.destination_warehouse_id, item.product_id, item.batch_id,
                float(item.quantity), "transfer_in", "stock_transfer", transfer.id,
            )

        transfer.status = "received"
        transfer.received_at = datetime.now(timezone.utc)
        self.db.flush()
        return transfer

    def list_transfers(self, organization_id: uuid.UUID) -> list[StockTransfer]:
        return self.transfers.list(organization_id)

    def get_transfer_or_404(self, transfer_id: uuid.UUID) -> StockTransfer:
        transfer = self.transfers.get(transfer_id)
        if transfer is None:
            raise NotFoundError(f"Stock transfer {transfer_id} not found")
        return transfer
