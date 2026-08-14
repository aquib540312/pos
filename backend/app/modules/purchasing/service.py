import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.numbering import next_document_number
from app.models.catalog import Product, ProductBatch
from app.models.organization import Branch, Warehouse
from app.models.party import Supplier
from app.models.purchasing import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseReturn,
    PurchaseReturnItem,
)
from app.modules.accounting.service import AccountingService
from app.modules.catalog.repository import HSNRepository
from app.modules.gst.service import compute_line_tax, is_inter_state_supply
from app.modules.inventory.service import InventoryService
from app.modules.purchasing.repository import GoodsReceiptRepository, PurchaseOrderRepository


class PurchasingService:
    def __init__(self, db: Session):
        self.db = db
        self.purchase_orders = PurchaseOrderRepository(db)
        self.goods_receipts = GoodsReceiptRepository(db)
        self.inventory = InventoryService(db)
        self.accounting = AccountingService(db)

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
        that PO's quantity_received. Purchase-side GST is captured per
        line (from the product's HSN rate unless overridden), so Input
        CGST/SGST/IGST credit can be posted to the ledger. This is the
        single transaction boundary where purchased stock becomes sellable."""
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
        if po is not None and po.status == "cancelled":
            raise ConflictError(f"Purchase order {po.po_number} is cancelled -- cannot receive against it")
        po_items_by_product = {i.product_id: i for i in po.items} if po else {}
        total_cost = 0.0
        total_input_cgst = total_input_sgst = total_input_igst = 0.0

        branch = self._branch_for_warehouse(warehouse_id)
        supplier = self.db.get(Supplier, supplier_id)
        inter_state = is_inter_state_supply(branch.state_code, supplier.state_code)

        for idx, item in enumerate(items):
            total_qty = float(item["quantity"])
            free_qty = float(item.get("free_quantity", 0))
            paid_qty = total_qty - free_qty
            # A supplier bonus/scheme (e.g. "10+1 free") spreads the same
            # invoiced cost across more physical units -- the batch's
            # landed cost per unit is lower than the invoiced unit_cost,
            # while unit_cost itself stays the actual invoiced rate.
            effective_unit_cost = (paid_qty * float(item["unit_cost"])) / total_qty if total_qty else 0.0

            product = self.db.get(Product, item["product_id"])
            hsn_code_id = product.hsn_code_id if product else None
            tax_rate_percent = item.get("tax_rate_percent")
            if tax_rate_percent is None and product is not None and product.hsn_code_id is not None:
                rate = HSNRepository(self.db).get_effective_tax_rate(product.hsn_code_id, grn.received_at.date())
                tax_rate_percent = float(rate.rate_percent) if rate else 0.0
            tax_rate_percent = float(tax_rate_percent or 0.0)

            breakdown = compute_line_tax(
                quantity=paid_qty, unit_price=item["unit_cost"], discount_amount=0,
                tax_rate_percent=tax_rate_percent, is_inter_state=inter_state,
            )

            batch = ProductBatch(
                organization_id=organization_id,
                product_id=item["product_id"],
                batch_number=item.get("batch_number") or f"{grn.grn_number}-{idx + 1}",
                expiry_date=item.get("expiry_date"),
                purchase_price=effective_unit_cost,
            )
            self.db.add(batch)
            self.db.flush()

            grn_item = GoodsReceiptItem(
                goods_receipt_id=grn.id,
                product_id=item["product_id"],
                batch_id=batch.id,
                quantity=total_qty,
                free_quantity=free_qty,
                unit_cost=item["unit_cost"],
                hsn_code_id=hsn_code_id,
                tax_rate_percent=tax_rate_percent,
                cgst_amount=breakdown.cgst_amount,
                sgst_amount=breakdown.sgst_amount,
                igst_amount=breakdown.igst_amount,
            )
            self.db.add(grn_item)
            self.db.flush()

            self.inventory.receive(
                organization_id=organization_id,
                warehouse_id=warehouse_id,
                product_id=item["product_id"],
                batch_id=batch.id,
                quantity=total_qty,
                movement_type="purchase_receipt",
                reference_type="goods_receipt",
                reference_id=grn.id,
            )

            po_item = po_items_by_product.get(item["product_id"])
            if po_item is not None:
                po_item.quantity_received = float(po_item.quantity_received) + paid_qty

            line_cost = paid_qty * float(item["unit_cost"])
            total_cost += line_cost
            total_input_cgst += breakdown.cgst_amount
            total_input_sgst += breakdown.sgst_amount
            total_input_igst += breakdown.igst_amount

        if po is not None and all(float(i.quantity_received) >= float(i.quantity_ordered) for i in po.items):
            po.status = "received"

        supplier.payable_balance = float(supplier.payable_balance) + total_cost + total_input_cgst + total_input_sgst + total_input_igst
        self.accounting.post_goods_receipt(grn, total_cost, total_input_cgst, total_input_sgst, total_input_igst)

        self.db.flush()
        return self.goods_receipts.get(grn.id)

    def _branch_for_warehouse(self, warehouse_id: uuid.UUID) -> Branch:
        warehouse = self.db.get(Warehouse, warehouse_id)
        if warehouse is None:
            raise NotFoundError(f"Warehouse {warehouse_id} not found")
        branch = self.db.get(Branch, warehouse.branch_id)
        if branch is None:
            raise NotFoundError(f"Branch for warehouse {warehouse_id} not found")
        return branch

    def update_po_status(self, organization_id: uuid.UUID, po_id: uuid.UUID, new_status: str) -> PurchaseOrder:
        po = self.purchase_orders.get(po_id)
        if po is None or po.organization_id != organization_id:
            raise NotFoundError(f"Purchase order {po_id} not found")
        allowed: dict[str, set[str]] = {
            "draft": {"submitted"},
            "submitted": {"cancelled", "closed", "received"},
            "received": {"closed"},
            "closed": set(),
            "cancelled": set(),
        }
        if new_status not in allowed.get(po.status, set()):
            raise ConflictError(f"Cannot move purchase order {po.po_number} from '{po.status}' to '{new_status}'")
        po.status = new_status
        self.db.flush()
        return po

    def pending_grn(self, organization_id: uuid.UUID) -> list[dict]:
        """Under-delivered purchase orders: every line where quantity_received
        is still below quantity_ordered, and the PO is not cancelled/closed.
        This is the server-side 'pending GRN' view the frontend can render
        to show which ordered goods are still owed."""
        stmt = (
            select(PurchaseOrder, Product)
            .join(PurchaseOrderItem, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .join(Product, Product.id == PurchaseOrderItem.product_id)
            .where(
                PurchaseOrder.organization_id == organization_id,
                PurchaseOrder.status.in_(["submitted", "draft"]),
                PurchaseOrderItem.quantity_received < PurchaseOrderItem.quantity_ordered,
            )
            .order_by(PurchaseOrder.order_date, PurchaseOrder.po_number)
        )
        rows = []
        for po, product in self.db.execute(stmt).all():
            for item in po.items:
                if item.product_id != product.id:
                    continue
                if float(item.quantity_received) >= float(item.quantity_ordered):
                    continue
                rows.append(
                    {
                        "po_id": po.id,
                        "po_number": po.po_number,
                        "supplier_id": po.supplier_id,
                        "order_date": po.order_date,
                        "status": po.status,
                        "product_id": product.id,
                        "product_name": product.name,
                        "sku": product.sku,
                        "quantity_ordered": float(item.quantity_ordered),
                        "quantity_received": float(item.quantity_received),
                        "outstanding_quantity": round(float(item.quantity_ordered) - float(item.quantity_received), 3),
                    }
                )
        return rows

    def create_purchase_return(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        supplier_id: uuid.UUID,
        reason: str | None,
        items: list[dict],
    ) -> PurchaseReturn:
        """Return damaged/excess goods to a supplier. Issues stock from the
        warehouse (movement_type 'purchase_return'), reduces the supplier's
        payable, and posts the reverse-of-GRN ledger entry (credit Inventory
        + Input GST, debit Accounts Payable)."""
        supplier = self.db.get(Supplier, supplier_id)
        if supplier is None or supplier.organization_id != organization_id:
            raise NotFoundError(f"Supplier {supplier_id} not found")

        branch = self.db.get(Branch, branch_id)
        warehouse = self.db.get(Warehouse, warehouse_id)
        if branch is None or branch.organization_id != organization_id:
            raise NotFoundError(f"Branch {branch_id} not found")
        if warehouse is None:
            raise NotFoundError(f"Warehouse {warehouse_id} not found")

        purchase_return = PurchaseReturn(
            organization_id=organization_id,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            supplier_id=supplier_id,
            return_number=next_document_number(self.db, PurchaseReturn, "PRN"),
            return_date=datetime.now(timezone.utc),
            reason=reason,
            is_debit_note=True,
        )
        self.db.add(purchase_return)
        self.db.flush()

        return_total = 0.0
        for item in items:
            batch_id = item.get("batch_id")
            grn_item = None
            if item.get("original_grn_item_id") and batch_id is None:
                grn_item = self.db.get(GoodsReceiptItem, item["original_grn_item_id"])
                if grn_item is None:
                    raise NotFoundError(f"GRN line {item['original_grn_item_id']} not found")
                batch_id = grn_item.batch_id
                if batch_id is None:
                    raise ValidationError("The linked GRN line has no batch to return from")

            self.inventory.issue(
                organization_id, warehouse_id, item["product_id"], batch_id, float(item["quantity"]),
                "purchase_return", "purchase_return", purchase_return.id,
            )

            unit_cost = float(item.get("unit_cost") or 0.0)
            taxable_value = round(float(item["quantity"]) * unit_cost, 2)
            if grn_item is not None:
                fraction = float(item["quantity"]) / float(grn_item.quantity)
                cgst = round(float(grn_item.cgst_amount) * fraction, 2)
                sgst = round(float(grn_item.sgst_amount) * fraction, 2)
                igst = round(float(grn_item.igst_amount) * fraction, 2)
            else:
                cgst = sgst = igst = 0.0
            line_total = round(taxable_value + cgst + sgst + igst, 2)

            self.db.add(
                PurchaseReturnItem(
                    purchase_return_id=purchase_return.id,
                    original_grn_item_id=item.get("original_grn_item_id"),
                    product_id=item["product_id"],
                    batch_id=batch_id,
                    quantity=item["quantity"],
                    unit_cost=unit_cost,
                    taxable_value=taxable_value,
                    cgst_amount=cgst,
                    sgst_amount=sgst,
                    igst_amount=igst,
                    line_total=line_total,
                )
            )
            return_total += line_total

        purchase_return.return_total = round(return_total, 2)
        supplier.payable_balance = max(0.0, float(supplier.payable_balance) - return_total)
        self.accounting.post_purchase_return(
            organization_id, purchase_return.id, purchase_return.return_date.date(),
            purchase_return.return_number,
            round(sum(float(i.taxable_value) for i in purchase_return.items), 2),
            round(sum(float(i.cgst_amount) for i in purchase_return.items), 2),
            round(sum(float(i.sgst_amount) for i in purchase_return.items), 2),
            round(sum(float(i.igst_amount) for i in purchase_return.items), 2),
        )
        self.db.flush()
        return purchase_return

    def list_purchase_returns(self, organization_id: uuid.UUID) -> list[PurchaseReturn]:
        stmt = (
            select(PurchaseReturn)
            .where(PurchaseReturn.organization_id == organization_id)
            .order_by(PurchaseReturn.return_date.desc())
        )
        return list(self.db.execute(stmt).scalars())

    def get_purchase_return_or_404(self, organization_id: uuid.UUID, purchase_return_id: uuid.UUID) -> PurchaseReturn:
        purchase_return = self.db.get(PurchaseReturn, purchase_return_id)
        if purchase_return is None or purchase_return.organization_id != organization_id:
            raise NotFoundError(f"Purchase return {purchase_return_id} not found")
        return purchase_return
