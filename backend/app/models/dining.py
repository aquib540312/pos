import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, branch_fk, org_fk

if TYPE_CHECKING:
    from app.models.party import Customer


class DiningTable(Base, UUIDPKMixin, TimestampMixin):
    """A physical table in the restaurant seating plan. Occupancy is tracked
    on the table (`status`) so a waiter can see available/occupied/reserved/
    cleaning at a glance, and is kept in sync by the dining service when an
    order opens (occupied) or closes (available)."""

    __tablename__ = "dining_tables"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "branch_id", "table_number", name="uq_dining_table_org_branch_number"
        ),
    )

    organization_id: Mapped[uuid.UUID] = org_fk()
    branch_id: Mapped[uuid.UUID] = branch_fk()

    table_number: Mapped[str] = mapped_column(String(20), nullable=False)
    # Free-text label ("Window table") so table_number can stay as the
    # short seat identifier printed on the KOT and bill.
    name: Mapped[str | None] = mapped_column(String(120))
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    # available|occupied|reserved|cleaning
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)

    orders: Mapped[list["TableOrder"]] = relationship(back_populates="table")


class TableOrder(Base, UUIDPKMixin, TimestampMixin):
    """A running guest bill at a table. Items are added while the party is
    seated; only when the bill is settled are they replayed through the
    ordinary SalesService.create_sale flow (same GST/stock/accounting
    machinery as a counter sale) and the resulting invoice id recorded here.
    An order belonging to the same table as a still-open other is prevented
    in the service layer, not by an index."""

    __tablename__ = "table_orders"

    __table_args__ = (
        # Concurrency guard: a table can host at most ONE open order at a
        # time. A partial (WHERE status='open') unique index enforces this
        # at the database level, so two waiters opening the same table
        # simultaneously cannot both succeed -- the second insert fails
        # with a unique violation instead of silently creating a second
        # open bill. Postgres and SQLite support partial indexes natively.
        Index(
            "uq_table_orders_one_open_per_table",
            "table_id",
            unique=True,
            sqlite_where=text("status = 'open'"),
            postgresql_where=text("status = 'open'"),
        ),
    )

    organization_id: Mapped[uuid.UUID] = org_fk()
    branch_id: Mapped[uuid.UUID] = branch_fk()
    # NULL only for parcel/takeaway orders (order_type='parcel') -- those
    # don't occupy a seat.
    table_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("dining_tables.id"), nullable=True, index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("customers.id"), nullable=True)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("shifts.id"), nullable=True)
    # Set once the bill is settled with a real invoice; null until then.
    sales_invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("sales_invoices.id"), nullable=True
    )

    # open|paid|cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    # dine_in|parcel -- a parcel order records no table and is settled at the
    # counter (takeaway), while dine_in occupies a room table.
    order_type: Mapped[str] = mapped_column(String(20), nullable=False, default="dine_in")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Number of kitchen tickets already emitted for this order -- each
    # "send to kitchen" batch gets the next sequential KOT number.
    kot_counter: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(String(255))

    table: Mapped["DiningTable | None"] = relationship(back_populates="orders")
    customer: Mapped["Customer | None"] = relationship("Customer")
    items: Mapped[list["TableOrderItem"]] = relationship(back_populates="order", order_by="TableOrderItem.created_at")


class TableOrderItem(Base, UUIDPKMixin, TimestampMixin):
    """One ordered line. `unit_price` is snapshotted from the product's
    sale_price at order time (not at settle), so a mid-meal price change
    cannot silently alter the guest's bill. Kitchen state lives on the line:
    `status` pending -> preparing -> served (or cancelled before serving)
    and `kot_number` records which kitchen ticket carried it."""

    __tablename__ = "table_order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("table_orders.id"), nullable=False, index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(14, 3, asdecimal=False), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    # pending|preparing|served|cancelled
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # e.g. "KOT-1"; shared by every line sent in the same kitchen batch.
    kot_number: Mapped[str | None] = mapped_column(String(20))
    sent_to_kitchen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Cook instructions ("less spicy", "extra cheese"...).
    note: Mapped[str | None] = mapped_column(String(255))

    order: Mapped["TableOrder"] = relationship(back_populates="items")

    @property
    def line_total(self) -> float:
        return round(float(self.quantity) * float(self.unit_price) - float(self.discount_amount), 2)
