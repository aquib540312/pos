import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, branch_fk, org_fk


class PurchaseOrder(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "purchase_orders"

    organization_id: Mapped[uuid.UUID] = org_fk()
    branch_id: Mapped[uuid.UUID] = branch_fk()
    supplier_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("suppliers.id"), nullable=False, index=True)
    po_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft|submitted|received|cancelled
    notes: Mapped[str | None] = mapped_column(String(500))

    items: Mapped[list["PurchaseOrderItem"]] = relationship(back_populates="purchase_order")


class PurchaseOrderItem(Base, UUIDPKMixin):
    __tablename__ = "purchase_order_items"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("purchase_orders.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    quantity_ordered: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)
    quantity_received: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False, default=0)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="items")


class GoodsReceipt(Base, UUIDPKMixin, TimestampMixin):
    """A GRN. Posting a GRN is the single point where purchase stock enters
    the warehouse: it creates/updates ProductBatch rows, writes
    StockLedgerEntry(movement_type="purchase_receipt") rows, and updates
    StockItem balances -- all inside one DB transaction."""

    __tablename__ = "goods_receipts"

    organization_id: Mapped[uuid.UUID] = org_fk()
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("purchase_orders.id"), nullable=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("warehouses.id"), nullable=False)
    supplier_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("suppliers.id"), nullable=False)
    grn_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supplier_invoice_number: Mapped[str | None] = mapped_column(String(60))

    items: Mapped[list["GoodsReceiptItem"]] = relationship(back_populates="goods_receipt")


class GoodsReceiptItem(Base, UUIDPKMixin):
    __tablename__ = "goods_receipt_items"

    goods_receipt_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("goods_receipts.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("product_batches.id"), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)
    # Bonus/free pieces included within `quantity` (e.g. a supplier's "10+1
    # free" scheme) -- physically received and sellable like the rest of
    # the batch, but not owed to the supplier. paid_quantity = quantity -
    # free_quantity is what actually costs money and counts toward a
    # linked PO's fulfillment; see PurchasingService.receive_goods.
    free_quantity: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False, default=0)
    unit_cost: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)

    goods_receipt: Mapped["GoodsReceipt"] = relationship(back_populates="items")
