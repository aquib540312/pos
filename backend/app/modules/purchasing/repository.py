from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.purchasing import GoodsReceipt, PurchaseOrder, PurchaseOrderItem


class PurchaseOrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, po_id: uuid.UUID) -> PurchaseOrder | None:
        stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id).options(selectinload(PurchaseOrder.items))
        return self.db.execute(stmt).scalars().first()

    def list(self, organization_id: uuid.UUID) -> list[PurchaseOrder]:
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.organization_id == organization_id)
            .options(selectinload(PurchaseOrder.items))
        )
        return list(self.db.execute(stmt).scalars())

    def add(self, po: PurchaseOrder) -> PurchaseOrder:
        self.db.add(po)
        self.db.flush()
        return po

    def add_item(self, item: PurchaseOrderItem) -> PurchaseOrderItem:
        self.db.add(item)
        self.db.flush()
        return item


class GoodsReceiptRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, grn: GoodsReceipt) -> GoodsReceipt:
        self.db.add(grn)
        self.db.flush()
        return grn

    def get(self, grn_id: uuid.UUID) -> GoodsReceipt | None:
        stmt = select(GoodsReceipt).where(GoodsReceipt.id == grn_id).options(selectinload(GoodsReceipt.items))
        return self.db.execute(stmt).scalars().first()

    def list(self, organization_id: uuid.UUID) -> list[GoodsReceipt]:
        stmt = (
            select(GoodsReceipt)
            .where(GoodsReceipt.organization_id == organization_id)
            .options(selectinload(GoodsReceipt.items))
            .order_by(GoodsReceipt.received_at.desc())
        )
        return list(self.db.execute(stmt).scalars())
