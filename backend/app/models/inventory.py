import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, org_fk


class StockItem(Base, UUIDPKMixin, TimestampMixin):
    """Current on-hand quantity for a (warehouse, product, batch) triple.

    This is a derived/cached balance -- the source of truth is the append-
    only StockLedgerEntry log below. Keeping a materialized balance avoids
    summing the whole ledger on every billing-screen stock check, and is
    updated transactionally in the same DB transaction as each ledger entry.
    """

    __tablename__ = "stock_items"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "product_id", "batch_id", name="uq_stock_warehouse_product_batch"),
    )

    organization_id: Mapped[uuid.UUID] = org_fk()
    warehouse_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("warehouses.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("product_batches.id"), nullable=True)
    quantity_on_hand: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False, default=0)


class StockLedgerEntry(Base, UUIDPKMixin):
    """Immutable, append-only movement log. Every stock change (purchase
    receipt, sale, return, transfer, adjustment) writes exactly one row
    here; StockItem.quantity_on_hand is maintained as a running total in the
    same transaction. Never updated or deleted -- corrections are posted as
    new offsetting entries, which is what makes stock audits trustworthy."""

    __tablename__ = "stock_ledger_entries"

    organization_id: Mapped[uuid.UUID] = org_fk()
    warehouse_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("warehouses.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False, index=True)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("product_batches.id"), nullable=True)

    movement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # purchase_receipt | sale | sale_return | purchase_return | transfer_out
    # | transfer_in | adjustment_in | adjustment_out
    quantity_delta: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)  # signed
    reference_type: Mapped[str] = mapped_column(String(30), nullable=False)  # e.g. "sales_invoice"
    reference_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    notes: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StockTransfer(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "stock_transfers"

    organization_id: Mapped[uuid.UUID] = org_fk()
    transfer_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    source_warehouse_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("warehouses.id"), nullable=False)
    destination_warehouse_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("warehouses.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft|dispatched|received
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["StockTransferItem"]] = relationship(back_populates="transfer")


class StockTransferItem(Base, UUIDPKMixin):
    __tablename__ = "stock_transfer_items"

    transfer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("stock_transfers.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("product_batches.id"), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)

    transfer: Mapped["StockTransfer"] = relationship(back_populates="items")
