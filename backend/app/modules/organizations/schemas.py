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
