import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, org_fk


class Category(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("organization_id", "name", "parent_id", name="uq_category_org_name_parent"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("categories.id"), nullable=True)


class UnitOfMeasure(Base, UUIDPKMixin):
    __tablename__ = "units_of_measure"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_uom_org_code"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    code: Mapped[str] = mapped_column(String(10), nullable=False)  # PCS, KG, LTR, BOX...
    name: Mapped[str] = mapped_column(String(50), nullable=False)


class HSNCode(Base, UUIDPKMixin):
    """HSN (goods) / SAC (services) reference code. GST rate is looked up via
    TaxRate, versioned separately, since the same HSN's rate can change over
    time by government notification."""

    __tablename__ = "hsn_codes"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_hsn_org_code"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    code: Mapped[str] = mapped_column(String(8), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    is_service: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # SAC vs HSN


class TaxRate(Base, UUIDPKMixin):
    """A GST slab applicable to an HSN/SAC code for a date range.

    `rate_percent` is the *total* GST rate (e.g. 18.00). Intra-state splits
    into CGST+SGST at rate/2 each; inter-state charges the full rate as
    IGST. See app/modules/gst/service.py for the split logic -- it is
    computed at invoice time, never stored as a precomputed CGST/SGST column
    here, because the same rate row is reused for both intra- and
    inter-state sales.
    """

    __tablename__ = "tax_rates"

    organization_id: Mapped[uuid.UUID] = org_fk()
    hsn_code_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("hsn_codes.id"), nullable=False, index=True)
    rate_percent: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=False)
    cess_percent: Mapped[float] = mapped_column(Numeric(5, 2, asdecimal=False), nullable=False, default=0)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)

    hsn_code: Mapped["HSNCode"] = relationship()


class Product(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("organization_id", "sku", name="uq_product_org_sku"),
        UniqueConstraint("organization_id", "barcode", name="uq_product_org_barcode"),
    )

    organization_id: Mapped[uuid.UUID] = org_fk()
    category_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("categories.id"), nullable=True)
    hsn_code_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("hsn_codes.id"), nullable=True)
    uom_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("units_of_measure.id"), nullable=False)

    sku: Mapped[str] = mapped_column(String(64), nullable=False)
    barcode: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))

    mrp: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    sale_price: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    purchase_price: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)

    tracks_batches: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tracks_serials: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tracks_expiry: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    reorder_level: Mapped[float] = mapped_column(Numeric(12, 3, asdecimal=False), nullable=False, default=0)
    is_combo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    hsn_code: Mapped["HSNCode | None"] = relationship()
    uom: Mapped["UnitOfMeasure"] = relationship()
    combo_components: Mapped[list["ComboComponent"]] = relationship(
        foreign_keys="ComboComponent.combo_product_id", back_populates="combo_product"
    )


class ComboComponent(Base, UUIDPKMixin):
    """Line items that make up a combo/bundle product. Selling one unit of
    the combo product decrements stock of each component by
    quantity * component_quantity (see inventory posting in sales service)."""

    __tablename__ = "combo_components"

    combo_product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False, index=True)
    component_product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 3, asdecimal=False), nullable=False, default=1)

    combo_product: Mapped["Product"] = relationship(foreign_keys=[combo_product_id], back_populates="combo_components")
    component_product: Mapped["Product"] = relationship(foreign_keys=[component_product_id])


class ProductBatch(Base, UUIDPKMixin, TimestampMixin):
    """A received batch of a product, tracked for expiry (grocery/medical)
    and cost-layer traceability. Stock quantities are always tied to a
    batch row (even for non-expiry products we create one open-ended batch
    per GRN line) so FIFO/expiry-first issuing and stock ledger entries have
    a single consistent join key."""

    __tablename__ = "product_batches"
    __table_args__ = (UniqueConstraint("product_id", "batch_number", name="uq_batch_product_number"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False, index=True)
    batch_number: Mapped[str] = mapped_column(String(64), nullable=False)
    manufactured_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date, index=True)
    purchase_price: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)

    product: Mapped["Product"] = relationship()


class ProductSerial(Base, UUIDPKMixin, TimestampMixin):
    """Serial-tracked unit (electronics warranty tracking). One row per
    physical unit; `status` moves in_stock -> sold -> (returned)."""

    __tablename__ = "product_serials"
    __table_args__ = (UniqueConstraint("product_id", "serial_number", name="uq_serial_product_number"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    product_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("warehouses.id"), nullable=True)
    serial_number: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="in_stock")
    warranty_expiry: Mapped[date | None] = mapped_column(Date)

    product: Mapped["Product"] = relationship()
