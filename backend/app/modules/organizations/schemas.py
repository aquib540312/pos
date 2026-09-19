import uuid

from pydantic import BaseModel, Field


class BranchCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=255)
    business_type: str = Field(default="grocery", max_length=30)
    state_code: str = Field(min_length=2, max_length=2)
    gstin: str | None = None
    address: str | None = None


class WarehouseCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=255)
    is_default: bool = False


class WarehouseResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    is_default: bool

    model_config = {"from_attributes": True}


class BranchResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    business_type: str
    state_code: str
    warehouses: list[WarehouseResponse]

    model_config = {"from_attributes": True}


class OrganizationProfileUpdateRequest(BaseModel):
    """Partial update of the tenant's invoice/billing identity. Omitting a
    field leaves it unchanged; sending it as an empty string clears it (for
    the nullable string fields)."""

    legal_name: str | None = Field(default=None, min_length=1, max_length=255)
    trade_name: str | None = Field(default=None, min_length=1, max_length=255)
    gstin: str | None = Field(default=None, max_length=15)
    pan: str | None = Field(default=None, max_length=10)
    default_state_code: str | None = Field(default=None, min_length=2, max_length=2)
    phone: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=500)
    footer_note: str | None = Field(default=None, max_length=200)
    tax_mode: str | None = Field(default=None, max_length=10)
    qr_enabled: bool | None = None


class OrganizationProfileResponse(BaseModel):
    id: uuid.UUID
    legal_name: str
    trade_name: str
    gstin: str | None
    pan: str | None
    default_state_code: str
    phone: str | None
    address: str | None
    footer_note: str | None
    tax_mode: str
    has_logo: bool
    vat_number: str | None = None
    qr_enabled: bool = False
