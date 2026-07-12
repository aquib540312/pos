import uuid
from datetime import date

from pydantic import BaseModel, Field


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: uuid.UUID | None = None


class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class UOMCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=10)
    name: str = Field(min_length=1, max_length=50)


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
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category_id: uuid.UUID | None = None
    hsn_code_id: uuid.UUID | None = None
    uom_id: uuid.UUID
    mrp: float = Field(ge=0)
    sale_price: float = Field(ge=0)
    purchase_price: float = Field(ge=0, default=0)
    tracks_batches: bool = False
    tracks_serials: bool = False
    tracks_expiry: bool = False
    reorder_level: float = Field(ge=0, default=0)
    is_combo: bool = False
    combo_components: list[ComboComponentRequest] = Field(default_factory=list)


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
    mrp: float
    sale_price: float
    purchase_price: float
    tax_rate_percent: float | None
    tracks_batches: bool
    tracks_serials: bool
    tracks_expiry: bool
    is_active: bool
    is_combo: bool
    combo_components: list[ComboComponentResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}
