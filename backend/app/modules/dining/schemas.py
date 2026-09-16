import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TableCreateRequest(BaseModel):
    table_number: str = Field(min_length=1, max_length=20)
    name: str | None = Field(default=None, max_length=120)
    capacity: int = Field(default=4, ge=1, le=100)


class TableUpdateRequest(BaseModel):
    table_number: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, max_length=120)
    capacity: int | None = Field(default=None, ge=1, le=100)
    status: str | None = Field(
        default=None, pattern="^(available|occupied|reserved|cleaning)$"
    )


class TableResponse(BaseModel):
    id: uuid.UUID
    table_number: str
    name: str | None
    capacity: int
    status: str
    is_active: bool
    active_order_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class OrderOpenRequest(BaseModel):
    # Parcel/takeaway orders are table-less (order_type='parcel'); dine_in
    # orders require a table_id. Validate-via-service, not here, so the
    # rule lives in one place.
    table_id: uuid.UUID | None = None
    order_type: str = Field(
        default="dine_in", pattern="^(dine_in|parcel)$",
        description="dine_in occupies a room table; parcel is counter/takeaway (no table)",
    )
    customer_id: uuid.UUID | None = None
    shift_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=255)


class OrderItemRequest(BaseModel):
    product_id: uuid.UUID
    quantity: float = Field(gt=0)
    unit_price: float | None = Field(default=None, ge=0, description="Overrides product.sale_price if provided")
    discount_amount: float = Field(default=0, ge=0)
    note: str | None = Field(default=None, max_length=255)


class OrderAddItemsRequest(BaseModel):
    items: list[OrderItemRequest] = Field(min_length=1)


class OrderItemUpdateRequest(BaseModel):
    quantity: float | None = Field(default=None, gt=0)
    discount_amount: float | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=255)


class ServeItemsRequest(BaseModel):
    item_ids: list[uuid.UUID] = Field(min_length=1)


class CancelItemRequest(BaseModel):
    note: str | None = Field(default=None, max_length=255)


class TransferOrderRequest(BaseModel):
    target_table_id: uuid.UUID


class MergeOrdersRequest(BaseModel):
    target_order_id: uuid.UUID


class SplitOrderRequest(BaseModel):
    target_table_id: uuid.UUID
    item_ids: list[uuid.UUID] = Field(min_length=1)


class OrderSettleRequest(BaseModel):
    warehouse_id: uuid.UUID
    shift_id: uuid.UUID | None = None
    payments: list["PaymentInput"] = Field(default_factory=list)
    is_credit_sale: bool = False


class PaymentInput(BaseModel):
    method: str = Field(pattern="^(cash|card|upi|wallet|credit|gift_card)$")
    amount: float = Field(gt=0)
    reference: str | None = None


class OrderItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    quantity: float
    unit_price: float
    discount_amount: float
    line_total: float
    status: str
    kot_number: str | None
    note: str | None


class TableOrderResponse(BaseModel):
    id: uuid.UUID
    table_id: uuid.UUID | None
    table_number: str
    table_name: str | None
    customer_id: uuid.UUID | None
    customer_name: str | None
    status: str
    order_type: str
    opened_at: datetime
    closed_at: datetime | None
    kot_counter: int
    sales_invoice_id: uuid.UUID | None
    note: str | None
    subtotal: float
    discount_total: float
    items: list[OrderItemResponse]


class OrderEstimateResponse(BaseModel):
    order_id: uuid.UUID
    subtotal: float
    taxable_total: float
    discount_total: float
    cgst_total: float
    sgst_total: float
    igst_total: float
    cess_total: float
    round_off: float
    grand_total: float
    items: list[OrderItemResponse]


OrderSettleRequest.model_rebuild()
