import uuid
from datetime import datetime

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


class CustomerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    gstin: str | None = Field(default=None, max_length=15)
    state_code: str | None = Field(default=None, max_length=2)
    address: str | None = Field(default=None, max_length=500)
    is_credit_customer: bool | None = None
    credit_limit: float | None = Field(default=None, ge=0)
    is_active: bool | None = None
    remove_phone: bool = False
    remove_email: bool = False
    remove_gstin: bool = False
    remove_state_code: bool = False
    remove_address: bool = False


class CreditPaymentRequest(BaseModel):
    """A cash/card/UPI payment collected against a customer's outstanding
    credit balance (reduces Accounts Receivable)."""

    amount: float = Field(gt=0)
    method: str = Field(default="cash", pattern="^(cash|card|upi|wallet)$")
    reference: str | None = None


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
    is_active: bool

    model_config = {"from_attributes": True}


class SupplierCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = None
    email: str | None = None
    gstin: str | None = None
    state_code: str | None = None
    address: str | None = None


class SupplierUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    gstin: str | None = Field(default=None, max_length=15)
    state_code: str | None = Field(default=None, max_length=2)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    remove_phone: bool = False
    remove_email: bool = False
    remove_gstin: bool = False
    remove_state_code: bool = False
    remove_address: bool = False


class SupplierResponse(BaseModel):
    id: uuid.UUID
    name: str
    phone: str | None
    email: str | None
    gstin: str | None
    state_code: str | None
    payable_balance: float
    is_active: bool

    model_config = {"from_attributes": True}


class SupplierPaymentRequest(BaseModel):
    amount: float = Field(gt=0)
    method: str = Field(default="bank", pattern="^(cash|bank|card|upi)$")
    reference: str | None = None
    note: str | None = None


class SupplierPaymentResponse(BaseModel):
    id: uuid.UUID
    supplier_id: uuid.UUID
    amount: float
    method: str
    reference: str | None
    paid_at: datetime
    note: str | None
    outstanding_payable: float

    model_config = {"from_attributes": True}
