import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalog import ProductBatch
from app.models.inventory import StockItem, StockLedgerEntry


class StockRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_stock_item(
        self, warehouse_id: uuid.UUID, product_id: uuid.UUID, batch_id: uuid.UUID | None
    ) -> StockItem | None:
        stmt = select(StockItem).where(
            StockItem.warehouse_id == warehouse_id,
            StockItem.product_id == product_id,
            StockItem.batch_id == batch_id,
        )
        return self.db.execute(stmt).scalars().first()

    def get_or_create_stock_item(
        self, organization_id: uuid.UUID, warehouse_id: uuid.UUID, product_id: uuid.UUID, batch_id: uuid.UUID | None
    ) -> StockItem:
        item = self.get_stock_item(warehouse_id, product_id, batch_id)
        if item is None:
            item = StockItem(
                organization_id=organization_id,
                warehouse_id=warehouse_id,
                product_id=product_id,
                batch_id=batch_id,
                quantity_on_hand=0,
            )
            self.db.add(item)
            self.db.flush()
        return item

    def total_quantity(self, warehouse_id: uuid.UUID, product_id: uuid.UUID) -> float:
        stmt = select(StockItem).where(StockItem.warehouse_id == warehouse_id, StockItem.product_id == product_id)
        items = self.db.execute(stmt).scalars().all()
        return float(sum(float(i.quantity_on_hand) for i in items))

    def list_available_batches_fefo(self, warehouse_id: uuid.UUID, product_id: uuid.UUID) -> list[StockItem]:
        """Stock items with quantity > 0 for a product at a warehouse,
        ordered First-Expiry-First-Out (batches with no expiry sort last,
        oldest batch first among ties) -- the standard issuing order for
        grocery/medical/perishable retail."""
        stmt = (
            select(StockItem)
            .join(ProductBatch, ProductBatch.id == StockItem.batch_id, isouter=True)
            .where(
                StockItem.warehouse_id == warehouse_id,
                StockItem.product_id == product_id,
                StockItem.quantity_on_hand > 0,
            )
            .order_by(ProductBatch.expiry_date.is_(None), ProductBatch.expiry_date.asc(), ProductBatch.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars())

    def list_stock(self, organization_id: uuid.UUID, warehouse_id: uuid.UUID | None = None) -> list[StockItem]:
        stmt = select(StockItem).where(StockItem.organization_id == organization_id)
        if warehouse_id:
            stmt = stmt.where(StockItem.warehouse_id == warehouse_id)
        return list(self.db.execute(stmt).scalars())

    def write_ledger_entry(
        self,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        product_id: uuid.UUID,
        batch_id: uuid.UUID | None,
        movement_type: str,
        quantity_delta: float,
        reference_type: str,
        reference_id: uuid.UUID,
        notes: str | None = None,
    ) -> StockLedgerEntry:
        entry = StockLedgerEntry(
            organization_id=organization_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            batch_id=batch_id,
            movement_type=movement_type,
            quantity_delta=quantity_delta,
            reference_type=reference_type,
            reference_id=reference_id,
            notes=notes,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(entry)
        self.db.flush()
        return entry
