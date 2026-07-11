import uuid

from pydantic import BaseModel, Field


class CustomerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    state_code: str | None = None
    address: str | None = None
    is_credit_customer: bool = False
    credit_limit: float = Field(ge=0, default=0)


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None
    email: str | None
    gstin: str | None
    state_code: str | None
    is_credit_customer: bool
    credit_limit: float
    credit_balance: float
    loyalty_points_balance: float

    model_config = {"from_attributes": True}


class SupplierCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    state_code: str | None = None
    address: str | None = None


class SupplierResponse(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None
    email: str | None
    gstin: str | None
    state_code: str | None
    payable_balance: float

    model_config = {"from_attributes": True}
