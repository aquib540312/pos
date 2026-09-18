import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CustomerCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    name_arabic: str | None = Field(default=None, max_length=255)
    phone: str | None = None
    email: str | None = None
    vat_number: str | None = Field(default=None, max_length=15)  # Saudi VAT number
    cr_number: str | None = Field(default=None, max_length=20)  # Commercial Registration
    state_code: str | None = None
    address: str | None = None
    customer_type: str = Field(default="walk_in", pattern="^(walk_in|restaurant|hotel|catering|regular|wholesale)$")
    price_level: str = Field(default="retail", pattern="^(retail|wholesale|restaurant|vip|custom)$")
    is_credit_customer: bool = False
    credit_limit: float = Field(ge=0, default=0)
    payment_terms_days: int = Field(ge=0, default=0)


class CustomerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    name_arabic: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    vat_number: str | None = Field(default=None, max_length=15)
    cr_number: str | None = Field(default=None, max_length=20)
    state_code: str | None = Field(default=None, max_length=2)
    address: str | None = Field(default=None, max_length=500)
    customer_type: str | None = Field(default=None, pattern="^(walk_in|restaurant|hotel|catering|regular|wholesale)$")
    price_level: str | None = Field(default=None, pattern="^(retail|wholesale|restaurant|vip|custom)$")
    is_credit_customer: bool | None = None
    credit_limit: float | None = Field(default=None, ge=0)
    payment_terms_days: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    remove_phone: bool = False
    remove_email: bool = False
    remove_vat_number: bool = False
    remove_cr_number: bool = False
    remove_state_code: bool = False
    remove_address: bool = False


class CustomerPaymentRequest(BaseModel):
    amount: float = Field(gt=0)
    method: str = Field(default="cash", pattern="^(cash|card|bank_transfer)$")
    reference: str | None = None


class CustomerPaymentResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    amount: float
    method: str
    reference: str | None
    paid_at: datetime
    note: str | None

    model_config = {"from_attributes": True}


class CustomerResponse(BaseModel):
    id: uuid.UUID
    name: str
    name_arabic: str | None = None
    phone: str | None
    email: str | None
    vat_number: str | None = None
    cr_number: str | None = None
    state_code: str | None
    customer_type: str = "walk_in"
    price_level: str = "retail"
    is_credit_customer: bool
    credit_limit: float
    credit_balance: float
    payment_terms_days: int = 0
    outstanding_balance: float = 0
    total_purchases: float = 0
    last_purchase_date: datetime | None = None
    loyalty_points_balance: float
    is_active: bool

    model_config = {"from_attributes": True}


class SupplierCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    name_arabic: str | None = Field(default=None, max_length=255)
    phone: str | None = None
    email: str | None = None
    vat_number: str | None = Field(default=None, max_length=15)  # Saudi VAT number
    cr_number: str | None = Field(default=None, max_length=20)  # Commercial Registration
    state_code: str | None = None
    address: str | None = None


class SupplierUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    name_arabic: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=255)
    vat_number: str | None = Field(default=None, max_length=15)
    cr_number: str | None = Field(default=None, max_length=20)
    state_code: str | None = Field(default=None, max_length=2)
    address: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    remove_phone: bool = False
    remove_email: bool = False
    remove_vat_number: bool = False
    remove_cr_number: bool = False
    remove_state_code: bool = False
    remove_address: bool = False


class SupplierResponse(BaseModel):
    id: uuid.UUID
    name: str
    name_arabic: str | None = None
    phone: str | None
    email: str | None
    vat_number: str | None = None
    cr_number: str | None = None
    state_code: str | None
    address: str | None = None
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
