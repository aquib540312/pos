import uuid
from datetime import date

from pydantic import BaseModel, Field


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: uuid.UUID | None = None


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: uuid.UUID | None = None
    remove_parent: bool = False


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class UOMCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=50)


class UOMUpdateRequest(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=10)
    name: str | None = Field(default=None, min_length=1, max_length=50)


class UOMResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str

    model_config = {"from_attributes": True}


class HSNCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=8)
    description: str | None = None
    is_service: bool = False
    rate_percent: float = Field(ge=0, le=100)
    cess_percent: float = Field(default=0, ge=0, le=100)
    effective_from: date


class HSNUpdateRequest(BaseModel):
    code: str | None = Field(default=None, min_length=2, max_length=8)
    description: str | None = Field(default=None, max_length=255)
    is_service: bool | None = None
    # Only applied when provided (creates a *new* versioned TaxRate row so
    # historical invoices keep their old rates).
    rate_percent: float | None = Field(default=None, ge=0, le=100)
    cess_percent: float | None = Field(default=None, ge=0, le=100)
    effective_from: date | None = None
    remove_description: bool = False


class HSNResponse(BaseModel):
    id: uuid.UUID
    code: str
    description: str | None
    is_service: bool
    current_rate_percent: float | None

    model_config = {"from_attributes": True}


class ComboComponentRequest(BaseModel):
    component_product_id: uuid.UUID
    quantity: float = Field(gt=0, default=1)


class ProductCreateRequest(BaseModel):
    sku: str = Field(min_length=1, max_length=64)
    barcode: str | None = None
    generate_barcode: bool = False
    name: str = Field(min_length=1, max_length=255)
    name_arabic: str | None = Field(default=None, max_length=255)
    brand: str | None = Field(default=None, max_length=120)
    description: str | None = None
    category_id: uuid.UUID | None = None
    hsn_code_id: uuid.UUID | None = None
    uom_id: uuid.UUID
    supplier_id: uuid.UUID | None = None
    mrp: float = Field(ge=0)
    sale_price: float = Field(ge=0)
    wholesale_price: float = Field(ge=0, default=0)
    restaurant_price: float = Field(ge=0, default=0)
    vip_price: float = Field(ge=0, default=0)
    purchase_price: float = Field(ge=0, default=0)
    cost_per_kg: float = Field(ge=0, default=0)
    selling_price_per_kg: float = Field(ge=0, default=0)
    minimum_selling_quantity: float = Field(ge=0, default=0)
    tracks_batches: bool = False
    tracks_serials: bool = False
    tracks_expiry: bool = False
    is_weighted: bool = False
    reorder_level: float = Field(ge=0, default=0)
    low_stock_notify: bool = True
    is_combo: bool = False
    combo_components: list[ComboComponentRequest] = Field(default_factory=list)
    prices_gst_inclusive: bool = False
    loyalty_exempt: bool = False
    parent_product_id: uuid.UUID | None = None
    variant_label: str | None = Field(default=None, max_length=80)
    aliases: list[str] = Field(default_factory=list)
    initial_stock_qty: float = Field(ge=0, default=0)
    warehouse_id: uuid.UUID | None = None
    # Beef-specific fields
    beef_cut: str | None = Field(default=None, max_length=100)
    fresh_frozen: str | None = Field(default=None, max_length=20)
    local_imported: str | None = Field(default=None, max_length=20)
    country_of_origin: str | None = Field(default=None, max_length=100)
    storage_location: str | None = Field(default=None, max_length=100)


class ProductUpdateRequest(BaseModel):
    """Partial product edit. Only the fields provided are applied; None
    means 'leave unchanged' (use remove_barcode / remove_description to
    clear a nullable field explicitly)."""

    sku: str | None = Field(default=None, min_length=1, max_length=64)
    barcode: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    name_arabic: str | None = Field(default=None, max_length=255)
    brand: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    category_id: uuid.UUID | None = None
    hsn_code_id: uuid.UUID | None = None
    uom_id: uuid.UUID | None = None
    supplier_id: uuid.UUID | None = None
    mrp: float | None = Field(default=None, ge=0)
    sale_price: float | None = Field(default=None, ge=0)
    wholesale_price: float | None = Field(default=None, ge=0)
    restaurant_price: float | None = Field(default=None, ge=0)
    vip_price: float | None = Field(default=None, ge=0)
    purchase_price: float | None = Field(default=None, ge=0)
    cost_per_kg: float | None = Field(default=None, ge=0)
    selling_price_per_kg: float | None = Field(default=None, ge=0)
    minimum_selling_quantity: float | None = Field(default=None, ge=0)
    reorder_level: float | None = Field(default=None, ge=0)
    low_stock_notify: bool | None = None
    is_weighted: bool | None = None
    is_active: bool | None = None
    loyalty_exempt: bool | None = None
    prices_gst_inclusive: bool | None = None
    parent_product_id: uuid.UUID | None = None
    variant_label: str | None = Field(default=None, max_length=80)
    remove_barcode: bool = False
    remove_description: bool = False
    remove_brand: bool = False
    remove_variant: bool = False
    aliases: list[str] | None = None
    tracks_batches: bool | None = None
    tracks_serials: bool | None = None
    tracks_expiry: bool | None = None
    # Beef-specific fields
    beef_cut: str | None = Field(default=None, max_length=100)
    fresh_frozen: str | None = Field(default=None, max_length=20)
    local_imported: str | None = Field(default=None, max_length=20)
    country_of_origin: str | None = Field(default=None, max_length=100)
    storage_location: str | None = Field(default=None, max_length=100)


class ComboComponentResponse(BaseModel):
    component_product_id: uuid.UUID
    component_product_name: str
    quantity: float

    model_config = {"from_attributes": True}


class BulkImportRowResult(BaseModel):
    row: int
    sku: str | None
    status: str
    error: str | None = None


class BulkImportResponse(BaseModel):
    total: int
    created: int
    updated: int
    failed: int
    rows: list[BulkImportRowResult]


class ProductResponse(BaseModel):
    id: uuid.UUID
    sku: str
    barcode: str | None
    name: str
    name_arabic: str | None = None
    brand: str | None
    category_id: uuid.UUID | None
    category_name: str | None
    uom_id: uuid.UUID
    hsn_code_id: uuid.UUID | None
    supplier_id: uuid.UUID | None = None
    mrp: float
    sale_price: float
    wholesale_price: float
    restaurant_price: float = 0
    vip_price: float = 0
    purchase_price: float
    cost_per_kg: float = 0
    selling_price_per_kg: float = 0
    minimum_selling_quantity: float = 0
    tax_rate_percent: float | None
    tracks_batches: bool
    tracks_serials: bool
    tracks_expiry: bool
    is_weighted: bool
    low_stock_notify: bool
    reorder_level: float
    is_active: bool
    is_combo: bool
    combo_components: list[ComboComponentResponse] = Field(default_factory=list)
    prices_gst_inclusive: bool
    loyalty_exempt: bool
    parent_product_id: uuid.UUID | None
    variant_label: str | None
    image_path: str | None
    aliases: list[str] = Field(default_factory=list)
    # Beef-specific fields
    beef_cut: str | None = None
    fresh_frozen: str | None = None
    local_imported: str | None = None
    country_of_origin: str | None = None
    storage_location: str | None = None

    model_config = {"from_attributes": True}
