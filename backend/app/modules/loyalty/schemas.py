import uuid
from datetime import date

from pydantic import BaseModel, Field


class CouponCreateRequest(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    discount_type: str = Field(pattern="^(percent|flat)$")
    discount_value: float = Field(gt=0)
    min_order_value: float = Field(default=0, ge=0)
    max_redemptions: int | None = None
    valid_from: date
    valid_until: date | None = None


class CouponResponse(BaseModel):
    id: uuid.UUID
    code: str
    discount_type: str
    discount_value: float
    min_order_value: float
    times_redeemed: int
    max_redemptions: int | None
    is_active: bool

    model_config = {"from_attributes": True}


class CouponValidateRequest(BaseModel):
    code: str
    order_value: float = Field(ge=0)


class CouponValidateResponse(BaseModel):
    valid: bool
    discount_amount: float
    reason: str | None = None


class GiftCardIssueRequest(BaseModel):
    card_number: str = Field(min_length=1, max_length=40)
    initial_value: float = Field(gt=0)
    issued_to_customer_id: uuid.UUID | None = None
    expires_on: date | None = None


class GiftCardResponse(BaseModel):
    id: uuid.UUID
    card_number: str
    initial_value: float
    balance: float
    is_active: bool

    model_config = {"from_attributes": True}


class GiftCardRedeemRequest(BaseModel):
    card_number: str
    amount: float = Field(gt=0)
    invoice_id: uuid.UUID | None = None
