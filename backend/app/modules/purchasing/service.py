import uuid
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.numbering import next_document_number
from app.models.catalog import ProductBatch
from app.models.purchasing import GoodsReceipt, GoodsReceiptItem, PurchaseOrder, PurchaseOrderItem
from app.modules.inventory.service import InventoryService
from app.modules.purchasing.repository import GoodsReceiptRepository, PurchaseOrderRepository


class PurchasingService:
    def __init__(self, db: Session):
        self.db = db
        self.purchase_orders = PurchaseOrderRepository(db)
        self.goods_receipts = GoodsReceiptRepository(db)
        self.inventory = InventoryService(db)

    def create_purchase_order(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
        supplier_id: uuid.UUID,
        order_date: date,
        notes: str | None,
        items: list[dict],
    ) -> PurchaseOrder:
        po = PurchaseOrder(
            organization_id=organization_id,
            branch_id=branch_id,
            supplier_id=supplier_id,
            po_number=next_document_number(self.db, PurchaseOrder, "PO"),
            order_date=order_date,
            status="submitted",
            notes=notes,
        )
        self.purchase_orders.add(po)
        for item in items:
            self.purchase_orders.add_item(
                PurchaseOrderItem(
                    purchase_order_id=po.id,
                    product_id=item["product_id"],
                    quantity_ordered=item["quantity_ordered"],
                    unit_cost=item["unit_cost"],
                )
            )
        self.db.flush()
        return self.purchase_orders.get(po.id)

    def receive_goods(
        self,
        organization_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        supplier_id: uuid.UUID,
        purchase_order_id: uuid.UUID | None,
        supplier_invoice_number: str | None,
        items: list[dict],
    ) -> GoodsReceipt:
        """Posts a GRN: for every line, opens a new batch (see
        ProductBatch docstring for why this happens even for products that
        don't track expiry), writes the purchase_receipt stock ledger
        entry via InventoryService, and -- if linked to a PO -- advances
        that PO's quantity_received. This is the single transaction
        boundary where purchased stock becomes sellable."""
        grn = GoodsReceipt(
            organization_id=organization_id,
            purchase_order_id=purchase_order_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier_id,
            grn_number=next_document_number(self.db, GoodsReceipt, "GRN"),
            received_at=datetime.now(timezone.utc),
            supplier_invoice_number=supplier_invoice_number,
        )
        self.goods_receipts.add(grn)

        po = self.purchase_orders.get(purchase_order_id) if purchase_order_id else None
        po_items_by_product = {i.product_id: i for i in po.items} if po else {}

        for idx, item in enumerate(items):
            batch = ProductBatch(
                organization_id=organization_id,
                product_id=item["product_id"],
                batch_number=item.get("batch_number") or f"{grn.grn_number}-{idx + 1}",
                expiry_date=item.get("expiry_date"),
                purchase_price=item["unit_cost"],
            )
            self.db.add(batch)
            self.db.flush()

            grn_item = GoodsReceiptItem(
                goods_receipt_id=grn.id,
                product_id=item["product_id"],
                batch_id=batch.id,
                quantity=item["quantity"],
                unit_cost=item["unit_cost"],
            )
            self.db.add(grn_item)
            self.db.flush()

            self.inventory.receive(
                organization_id=organization_id,
                warehouse_id=warehouse_id,
                product_id=item["product_id"],
                batch_id=batch.id,
                quantity=item["quantity"],
                movement_type="purchase_receipt",
                reference_type="goods_receipt",
                reference_id=grn.id,
            )

            po_item = po_items_by_product.get(item["product_id"])
            if po_item is not None:
                po_item.quantity_received = float(po_item.quantity_received) + item["quantity"]

        if po is not None and all(float(i.quantity_received) >= float(i.quantity_ordered) for i in po.items):
            po.status = "received"

        self.db.flush()
        return self.goods_receipts.get(grn.id)
