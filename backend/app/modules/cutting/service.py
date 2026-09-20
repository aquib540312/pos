import uuid
from sqlalchemy.orm import Session
from app.models.cutting import CuttingOrder, CuttingOrderItem


class CuttingService:
    def __init__(self, db: Session):
        self.db = db

    def create_order(self, organization_id: uuid.UUID, source_product_id: uuid.UUID,
                     input_weight: float, items: list[dict], butcher_name: str | None = None,
                     notes: str | None = None) -> CuttingOrder:
        order = CuttingOrder(
            organization_id=organization_id,
            source_product_id=source_product_id,
            input_weight=input_weight,
            status="pending",
            notes=notes,
            butcher_name=butcher_name,
        )
        self.db.add(order)
        self.db.flush()

        for item_data in items:
            item = CuttingOrderItem(
                cutting_order_id=order.id,
                product_id=item_data["product_id"],
                output_weight=item_data["output_weight"],
                waste_weight=item_data.get("waste_weight", 0),
            )
            self.db.add(item)

        self.db.flush()
        return order

    def list_orders(self, organization_id: uuid.UUID) -> list[CuttingOrder]:
        return self.db.query(CuttingOrder).filter(
            CuttingOrder.organization_id == organization_id
        ).order_by(CuttingOrder.created_at.desc()).all()

    def complete_order(self, organization_id: uuid.UUID, order_id: uuid.UUID) -> CuttingOrder:
        order = self.db.query(CuttingOrder).filter_by(id=order_id).first()
        if not order or order.organization_id != organization_id:
            raise ValueError("Cutting order not found")
        if order.status != "pending":
            raise ValueError("Order is not in pending status")
        order.status = "completed"
        self.db.flush()
        return order
