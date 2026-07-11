import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SaleLineRequest(BaseModel):
    product_id: uuid.UUID
    quantity: float = Field(gt=0)
    unit_price: float | None = Field(default=None, ge=0, description="Overrides product.sale_price if provided")
    discount_amount: float = Field(default=0, ge=0)


class PaymentRequest(BaseModel):
    method: str = Field(pattern="^(cash|card|upi|wallet|credit|gift_card)$")
    amount: float = Field(gt=0)
    reference: str | None = None


class SaleCreateRequest(BaseModel):
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    shift_id: uuid.UUID | None = None
    items: list[SaleLineRequest] = Field(min_length=1)
    payments: list[PaymentRequest] = Field(default_factory=list)
    redeem_loyalty_points: float = Field(default=0, ge=0)
    is_credit_sale: bool = False


class SaleInvoiceItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    batch_id: uuid.UUID | None
    quantity: float
    unit_price: float
    discount_amount: float
    taxable_value: float
    tax_rate_percent: float
    cgst_amount: float
    sgst_amount: float
    igst_amount: float
    cess_amount: float
    line_total: float

    model_config = {"from_attributes": True}


class PaymentResponse(BaseModel):
    id: uuid.UUID
    method: str
    amount: float
    reference: str | None

    model_config = {"from_attributes": True}


class SaleInvoiceResponse(BaseModel):
    id: uuid.UUID
    invoice_number: str
    invoice_date: datetime
    branch_id: uuid.UUID
    customer_id: uuid.UUID | None
    place_of_supply_state_code: str
    is_inter_state: bool
    subtotal: float
    discount_total: float
    taxable_total: float
    cgst_total: float
    sgst_total: float
    igst_total: float
    cess_total: float
    round_off: float
    grand_total: float
    is_credit_sale: bool
    status: str
    loyalty_points_earned: float
    loyalty_points_redeemed: float
    items: list[SaleInvoiceItemResponse]
    payments: list[PaymentResponse]

    model_config = {"from_attributes": True}


class ReturnLineRequest(BaseModel):
    original_invoice_item_id: uuid.UUID
    quantity: float = Field(gt=0)


class ReturnCreateRequest(BaseModel):
    original_invoice_id: uuid.UUID
    reason: str | None = None
    refund_mode: str = Field(default="cash", pattern="^(cash|card|upi|wallet|credit_note)$")
    items: list[ReturnLineRequest] = Field(min_length=1)


class ReturnResponse(BaseModel):
    id: uuid.UUID
    return_number: str
    original_invoice_id: uuid.UUID
    refund_total: float
    refund_mode: str

    model_config = {"from_attributes": True}
