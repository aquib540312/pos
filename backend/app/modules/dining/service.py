import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.dining import DiningTable, TableOrder, TableOrderItem
from app.models.organization import Branch
from app.modules.catalog.repository import ProductRepository
from app.modules.dining.repository import DiningTableRepository, TableOrderRepository
from app.modules.gst.service import compute_line_tax, round_invoice_total
from app.modules.sales.repository import SalesInvoiceRepository
from app.modules.sales.service import SalesService

_TABLE_STATUS_ACTIVE = {"available", "occupied", "reserved", "cleaning"}
_ITEM_STATUS_ACTIVE = {"pending", "preparing", "ready", "served"}


class DiningService:
    """Restaurant dining domain: table seating and guest orders. Order items
    snapshot the unit price at order time; stock is NOT issued while items
    are being taken -- it only happens once the bill is settled and the
    order's lines are replayed through SalesService.create_sale (the same
    checkout pipeline a counter sale uses, so GST/stock/ledger are always
    consistent)."""

    def __init__(self, db: Session):
        self.db = db
        self.tables = DiningTableRepository(db)
        self.orders = TableOrderRepository(db)
        self.invoices = SalesInvoiceRepository(db)

    # ---------------- tables ----------------

    def list_tables(self, organization_id: uuid.UUID, branch_id: uuid.UUID) -> list[tuple[DiningTable, uuid.UUID | None]]:
        rows = self.tables.list_by_branch(organization_id, branch_id)
        return [(table, self._active_order_id(table.id)) for table in rows]

    def _active_order_id(self, table_id: uuid.UUID) -> uuid.UUID | None:
        order = self.tables.get_open_order_for_table(table_id)
        return order.id if order else None

    def create_table(
        self, organization_id: uuid.UUID, branch_id: uuid.UUID, table_number: str, name: str | None, capacity: int
    ) -> DiningTable:
        self._branch_or_404(organization_id, branch_id)
        existing = [t for t in self.tables.list_by_branch(organization_id, branch_id) if t.table_number == table_number]
        if existing:
            raise ConflictError(f"Table '{table_number}' already exists at this branch")
        return self.tables.add(
            DiningTable(
                organization_id=organization_id,
                branch_id=branch_id,
                table_number=table_number,
                name=name,
                capacity=capacity,
                status="available",
            )
        )

    def update_table(
        self,
        organization_id: uuid.UUID,
        table_id: uuid.UUID,
        table_number: str | None,
        name: str | None,
        capacity: int | None,
        status: str | None,
    ) -> DiningTable:
        table = self._get_table_or_404(organization_id, table_id)
        if table_number is not None and table_number != table.table_number:
            clash = [t for t in self.tables.list_by_branch(organization_id, table.branch_id) if t.table_number == table_number]
            if clash:
                raise ConflictError(f"Table '{table_number}' already exists at this branch")
            table.table_number = table_number
        if name is not None:
            table.name = name or None
        if capacity is not None:
            table.capacity = capacity
        if status is not None:
            if status == "occupied" and self._active_order_id(table.id) is None:
                raise ValidationError("Cannot mark a table occupied without an open order on it")
            table.status = status
        self.db.flush()
        return table

    def deactivate_table(self, organization_id: uuid.UUID, table_id: uuid.UUID) -> DiningTable:
        table = self._get_table_or_404(organization_id, table_id)
        if self._active_order_id(table.id) is not None:
            raise ConflictError(f"Table '{table.table_number}' has an open order -- settle it before deactivating")
        table.is_active = False
        self.db.flush()
        return table

    def _get_table_or_404(self, organization_id: uuid.UUID, table_id: uuid.UUID) -> DiningTable:
        table = self.tables.get(table_id)
        if table is None or table.organization_id != organization_id:
            raise NotFoundError(f"Table {table_id} not found")
        return table

    def _branch_or_404(self, organization_id: uuid.UUID, branch_id: uuid.UUID) -> Branch:
        branch = self.db.get(Branch, branch_id)
        if branch is None or branch.organization_id != organization_id:
            raise NotFoundError(f"Branch {branch_id} not found")
        return branch

    # ---------------- orders ----------------

    def open_order(
        self,
        organization_id: uuid.UUID,
        branch_id: uuid.UUID,
        table_id: uuid.UUID | None,
        order_type: str,
        customer_id: uuid.UUID | None,
        shift_id: uuid.UUID | None,
        note: str | None,
    ) -> TableOrder:
        branch = self._branch_or_404(organization_id, branch_id)
        if order_type == "parcel":
            # Counter/takeaway: no seat is held, no table lookup, and nothing
            # to mark occupied. The customer is optional (walk-ins settle cash
            # without a party record).
            order = self.orders.add(
                TableOrder(
                    organization_id=organization_id,
                    branch_id=branch.id,
                    table_id=None,
                    customer_id=customer_id,
                    shift_id=shift_id,
                    status="open",
                    order_type="parcel",
                    opened_at=datetime.now(timezone.utc),
                    note=note,
                )
            )
            self.db.flush()
            return self.orders.get_detailed(order.id)

        if table_id is None:
            raise ValidationError("A dine_in order requires a table_id")
        table = self.tables.get_for_update(table_id)
        if table is None or table.organization_id != organization_id:
            raise NotFoundError(f"Table {table_id} not found")
        if not table.is_active:
            raise ValidationError(f"Table '{table.table_number}' is deactivated")
        if self._active_order_id(table.id) is not None:
            raise ConflictError(f"Table '{table.table_number}' already has an open order")
        if branch.id != table.branch_id:
            raise ValidationError(
                f"Branch {branch_id} does not match the table's branch ({table.branch_id})"
            )
        order = self.orders.add(
            TableOrder(
                organization_id=organization_id,
                branch_id=table.branch_id,
                table_id=table_id,
                customer_id=customer_id,
                shift_id=shift_id,
                status="open",
                order_type="dine_in",
                opened_at=datetime.now(timezone.utc),
                note=note,
            )
        )
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError(f"Table '{table.table_number}' already has an open order") from None
        table.status = "occupied"
        self.db.flush()
        return self.orders.get_detailed(order.id)

    def _open_order_or_404(self, organization_id: uuid.UUID, order_id: uuid.UUID) -> TableOrder:
        order = self.orders.get_for_update(order_id)
        if order is None or order.organization_id != organization_id:
            raise NotFoundError(f"Order {order_id} not found")
        if order.status != "open":
            raise ConflictError(f"Order is already {order.status}")
        return order

    def add_items(
        self,
        organization_id: uuid.UUID,
        order_id: uuid.UUID,
        items: list[dict],
    ) -> TableOrder:
        order = self._open_order_or_404(organization_id, order_id)

        products = ProductRepository(self.db)
        for line in items:
            product = products.get(line["product_id"])
            if product is None or product.organization_id != organization_id:
                raise NotFoundError(f"Product {line['product_id']} not found")
            unit_price = line.get("unit_price") if line.get("unit_price") is not None else float(product.sale_price)
            quantity = float(line["quantity"])
            discount = float(line.get("discount_amount", 0))
            if discount > quantity * unit_price:
                raise ValidationError(
                    f"Discount ({discount}) cannot exceed line value for product '{product.name}'"
                )
            self.orders.add_item(
                TableOrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_price=unit_price,
                    discount_amount=discount,
                    note=line.get("note"),
                )
            )
        self.db.flush()
        return self.orders.get_detailed(order.id)

    def update_item(
        self,
        organization_id: uuid.UUID,
        order_id: uuid.UUID,
        item_id: uuid.UUID,
        quantity: float | None,
        discount_amount: float | None,
        note: str | None,
    ) -> TableOrder:
        order = self._open_order_or_404(organization_id, order_id)
        item = self._order_item_or_404(order, item_id)
        if item.status != "pending":
            raise ConflictError("Only a pending item (not yet sent to the kitchen) can be edited")
        if quantity is not None:
            if quantity <= 0:
                raise ValidationError("Quantity must be positive")
            if float(item.discount_amount) > quantity * float(item.unit_price):
                raise ValidationError("Discount cannot exceed line value")
            item.quantity = quantity
        if discount_amount is not None:
            if discount_amount < 0 or discount_amount > float(item.quantity) * float(item.unit_price):
                raise ValidationError("Discount cannot exceed line value")
            item.discount_amount = discount_amount
        if note is not None:
            item.note = note or None
        self.db.flush()
        return self.orders.get_detailed(order.id)

    def remove_item(self, organization_id: uuid.UUID, order_id: uuid.UUID, item_id: uuid.UUID) -> TableOrder:
        order = self._open_order_or_404(organization_id, order_id)
        item = self._order_item_or_404(order, item_id)
        if item.status != "pending":
            raise ConflictError("Only a pending item (not yet sent to the kitchen) can be removed")
        self.db.delete(item)
        self.db.flush()
        return self.orders.get_detailed(order.id)

    def _open_order_for_settle(self, organization_id: uuid.UUID, order_id: uuid.UUID) -> TableOrder:
        """Row-lock the order for settle. Allows open (settle now) as well as
        already-paid orders (idempotent re-settle returns the same invoice)."""
        order = self.orders.get_for_update(order_id)
        if order is None or order.organization_id != organization_id:
            raise NotFoundError(f"Order {order_id} not found")
        if order.status not in ("open", "paid"):
            raise ConflictError(f"Order is already {order.status}")
        return order

    def _order_item_or_404(self, order: TableOrder, item_id: uuid.UUID) -> TableOrderItem:
        for item in order.items:
            if item.id == item_id:
                return item
        raise NotFoundError(f"Item {item_id} not found on order {order.id}")

    def send_to_kitchen(self, organization_id: uuid.UUID, order_id: uuid.UUID) -> TableOrder:
        """Emit a kitchen ticket (KOT) for everything still pending on the
        order. One send = one sequential KOT number shared by the batch, so
        the smaller paper slip is easy for kitchen staff to follow."""
        order = self._open_order_or_404(organization_id, order_id)
        pending = [i for i in order.items if i.status == "pending"]
        if not pending:
            raise ValidationError("There are no pending items to send to the kitchen")
        order.kot_counter += 1
        kot_number = f"KOT-{order.kot_counter}"
        for item in pending:
            item.status = "preparing"
            item.kot_number = kot_number
            item.sent_to_kitchen_at = datetime.now(timezone.utc)
        self.db.flush()
        return self.orders.get_detailed(order.id)

    def mark_ready(self, organization_id: uuid.UUID, order_id: uuid.UUID, item_ids: list[uuid.UUID]) -> TableOrder:
        """Kitchen signals a cooked/plated line is ready to be served."""
        order = self._open_order_or_404(organization_id, order_id)
        wanted = set(item_ids)
        for item in order.items:
            if item.id in wanted:
                if item.status in ("cancelled", "served"):
                    raise ConflictError(f"An item that is {item.status} cannot be marked ready")
                if item.status == "pending":
                    raise ConflictError("A pending item (not yet sent to the kitchen) cannot be marked ready")
                item.status = "ready"
        self.db.flush()
        return self.orders.get_detailed(order.id)

    def mark_served(self, organization_id: uuid.UUID, order_id: uuid.UUID, item_ids: list[uuid.UUID]) -> TableOrder:
        order = self._open_order_or_404(organization_id, order_id)
        wanted = set(item_ids)
        for item in order.items:
            if item.id in wanted:
                if item.status == "cancelled":
                    raise ConflictError("A cancelled item cannot be marked served")
                if item.status == "pending":
                    raise ConflictError(
                        "A pending item has not been to the kitchen yet -- send it first"
                    )
                item.status = "served"
        self.db.flush()
        return self.orders.get_detailed(order.id)

    def cancel_item(
        self,
        organization_id: uuid.UUID,
        order_id: uuid.UUID,
        item_id: uuid.UUID,
        note: str | None = None,
    ) -> TableOrder:
        """Void a single line -- including one already sent to the kitchen.
        Keeps the line (status=cancelled) so the printed KOT and the audit
        trail always show what happened; a fresh send-to-kitchen will not
        re-print it. This is the audited path for undoing a KOT'd item."""
        order = self._open_order_or_404(organization_id, order_id)
        item = self._order_item_or_404(order, item_id)
        if item.status == "cancelled":
            raise ConflictError("Item is already cancelled")
        item.status = "cancelled"
        if note:
            item.note = (f"{item.note}; " if item.note else "") + f"VOID: {note}"
        elif item.note:
            item.note = f"VOID: {item.note}"
        self.db.flush()
        return self.orders.get_detailed(order.id)

    def cancel_order(self, organization_id: uuid.UUID, order_id: uuid.UUID, note: str | None = None) -> TableOrder:
        order = self._open_order_or_404(organization_id, order_id)
        for item in order.items:
            if item.status != "cancelled":
                item.status = "cancelled"
        order.status = "cancelled"
        order.note = note or order.note
        order.closed_at = datetime.now(timezone.utc)
        if order.table_id is not None:
            self._free_table(order.table_id)
        self.db.flush()
        return self.orders.get_detailed(order.id)

    # ---------------- billing ----------------

    def estimate(self, organization_id: uuid.UUID, order_id: uuid.UUID) -> tuple[TableOrder, dict]:
        """Full GST-computed bill preview using exactly the same tax
        functions SalesService.create_sale will use at settle time, so the
        amount shown is what the server will actually post (no client-side
        re-derivation drift)."""
        order = self._open_order_or_404(organization_id, order_id)

        from app.modules.catalog.repository import HSNRepository, ProductRepository

        products_repo = ProductRepository(self.db)
        hsn = HSNRepository(self.db)

        subtotal = discount_total = taxable_total = 0.0
        vat_total = 0.0
        items = []
        for item in order.items:
            if item.status == "cancelled":
                continue
            product = products_repo.get(item.product_id)
            if product is None or product.hsn_code_id is None:
                raise ValidationError(f"No effective VAT rate configured for product '{item.product_id}'")
            tax_rate = hsn.get_effective_tax_rate(product.hsn_code_id, datetime.now(timezone.utc).date())
            if tax_rate is None:
                raise ValidationError(f"No effective VAT rate configured for product '{item.product_id}'")
            breakdown = compute_line_tax(
                quantity=float(item.quantity),
                unit_price=float(item.unit_price),
                discount_amount=float(item.discount_amount),
                tax_rate_percent=float(tax_rate.rate_percent),
            )
            subtotal += float(item.quantity) * float(item.unit_price)
            discount_total += float(item.discount_amount)
            taxable_total += breakdown.taxable_value
            vat_total += breakdown.vat_amount
            items.append({
                "id": item.id,
                "product_id": item.product_id,
                "product_name": product.name,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "discount_amount": item.discount_amount,
                "line_total": breakdown.line_total,
                "status": item.status,
                "kot_number": item.kot_number,
                "note": item.note,
            })

        grand_total, round_off = round_invoice_total(taxable_total + vat_total)
        return order, {
            "order_id": order.id,
            "subtotal": subtotal,
            "taxable_total": taxable_total,
            "discount_total": discount_total,
            "vat_total": vat_total,
            "round_off": round_off,
            "grand_total": grand_total,
            "items": items,
        }

    def settle_order(
        self,
        organization_id: uuid.UUID,
        order_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        shift_id: uuid.UUID | None,
        payments: list[dict],
        is_credit_sale: bool,
    ) -> tuple[TableOrder, object]:
        order = self._open_order_for_settle(organization_id, order_id)
        # Idempotency guard: a settled order whose invoice link is present
        # returns the same invoice instead of double-billing the guest (e.g.
        # a client whose response was lost retries the settle).
        if order.status == "paid" and order.sales_invoice_id is not None:
            invoice = self.invoices.get(order.sales_invoice_id)
            if invoice is not None:
                return self.orders.get_detailed(order.id), invoice
        billable = [i for i in order.items if i.status != "cancelled"]
        if not billable:
            raise ValidationError("Order has no billable items to settle")

        invoice = SalesService(self.db).create_sale(
            organization_id=organization_id,
            branch_id=order.branch_id,
            warehouse_id=warehouse_id,
            customer_id=order.customer_id,
            shift_id=shift_id or order.shift_id,
            items=[
                {
                    "product_id": item.product_id,
                    "quantity": float(item.quantity),
                    "unit_price": float(item.unit_price),
                    "discount_amount": float(item.discount_amount),
                }
                for item in billable
            ],
            payments=payments,
            redeem_loyalty_points=0,
            is_credit_sale=is_credit_sale,
        )
        order.sales_invoice_id = invoice.id
        order.status = "paid"
        order.closed_at = datetime.now(timezone.utc)
        if order.table_id is not None:
            self._free_table(order.table_id)
        self.db.flush()
        return self.orders.get_detailed(order.id), invoice

    def transfer_order(
        self, organization_id: uuid.UUID, order_id: uuid.UUID, target_table_id: uuid.UUID
    ) -> TableOrder:
        """Move the whole party to another table; both tables must belong to
        the same branch and the target must be free."""
        order = self._open_order_or_404(organization_id, order_id)
        if order.table_id == target_table_id:
            return self.orders.get_detailed(order.id)
        target = self.tables.get(target_table_id)
        if target is None or target.organization_id != organization_id:
            raise NotFoundError(f"Table {target_table_id} not found")
        if target.branch_id != order.branch_id:
            raise ValidationError(
                f"Table '{target.table_number}' belongs to a different branch -- cannot transfer across branches"
            )
        if not target.is_active:
            raise ValidationError(f"Table '{target.table_number}' is deactivated")
        if target.status != "available":
            raise ConflictError(f"Table '{target.table_number}' is not available")
        # Release the source table and occupy the target.
        self._free_table(order.table_id)
        order.table_id = target.id
        target.status = "occupied"
        self.db.flush()
        return self.orders.get_detailed(order.id)

    def merge_orders(
        self, organization_id: uuid.UUID, source_order_id: uuid.UUID, target_order_id: uuid.UUID
    ) -> TableOrder:
        """Combine two open orders: every item from the source order is moved
        to the target order, the source order is closed (merge action is
        audited server-side) and its table is freed."""
        source = self._open_order_or_404(organization_id, source_order_id)
        target = self._open_order_or_404(organization_id, target_order_id)
        if source.id == target.id:
            raise ValidationError("Cannot merge an order into itself")
        if source.branch_id != target.branch_id:
            raise ValidationError("Orders from different branches cannot be merged")
        for item in source.items:
            item.order_id = target.id
        source.status = "cancelled"
        source.note = (f"{source.note}; " if source.note else "") + f"MERGED into order {target.id}"
        source.closed_at = datetime.now(timezone.utc)
        self._free_table(source.table_id)
        self.db.flush()
        return self.orders.get_detailed(target.id)

    def split_order(
        self,
        organization_id: uuid.UUID,
        source_order_id: uuid.UUID,
        target_table_id: uuid.UUID,
        item_ids: list[uuid.UUID],
    ) -> TableOrder:
        """Move a waiter-selected subset of pending items onto a fresh order
        opened on another table. Only pending (not yet KOT'd, not cancelled)
        lines may move so the kitchen slips stay truthful."""
        source = self._open_order_or_404(organization_id, source_order_id)
        target_table = self.tables.get(target_table_id)
        if target_table is None or target_table.organization_id != organization_id:
            raise NotFoundError(f"Table {target_table_id} not found")
        if target_table.branch_id != source.branch_id:
            raise ValidationError(
                f"Table '{target_table.table_number}' belongs to a different branch -- cannot split across branches"
            )
        if not target_table.is_active:
            raise ValidationError(f"Table '{target_table.table_number}' is deactivated")
        if target_table.status != "available":
            raise ConflictError(f"Table '{target_table.table_number}' is not available")
        wanted = set(item_ids)
        if not wanted:
            raise ValidationError("Select at least one item to split")
        move = []
        for item in source.items:
            if item.id in wanted:
                if item.status != "pending":
                    raise ConflictError(
                        f"Only pending items can be moved; item {item.product_id} "
                        f"is {item.status}"
                    )
                move.append(item)
        if not move:
            raise ValidationError("No matching pending items to split")
        target_table = self.tables.get_for_update(target_table_id)
        if target_table.status != "available":
            raise ConflictError(f"Table '{target_table.table_number}' is not available")
        try:
            new_order = self.orders.add(
                TableOrder(
                    organization_id=organization_id,
                    branch_id=source.branch_id,
                    table_id=target_table.id,
                    customer_id=source.customer_id,
                    shift_id=source.shift_id,
                    status="open",
                    opened_at=datetime.now(timezone.utc),
                )
            )
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            raise ConflictError(f"Table '{target_table.table_number}' already has an open order") from None
        for item in move:
            item.order_id = new_order.id
        target_table.status = "occupied"
        self.db.flush()
        return self.orders.get_detailed(new_order.id)

    def _free_table(self, table_id: uuid.UUID) -> None:
        table = self.tables.get(table_id)
        if table is not None and table.status == "occupied":
            table.status = "available"

    def get_order_or_404(self, organization_id: uuid.UUID, order_id: uuid.UUID) -> TableOrder:
        order = self.orders.get_detailed(order_id)
        if order is None or order.organization_id != organization_id:
            raise NotFoundError(f"Order {order_id} not found")
        return order

    def list_orders(self, organization_id: uuid.UUID, branch_id: uuid.UUID, status: str | None = None) -> list[TableOrder]:
        return self.orders.list_by_branch(organization_id, branch_id, status)
