import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class PurchaseOrderItemRequest(BaseModel):
    product_id: uuid.UUID
    quantity_ordered: float = Field(gt=0)
    unit_cost: float = Field(ge=0)


class PurchaseOrderCreateRequest(BaseModel):
    branch_id: uuid.UUID
    supplier_id: uuid.UUID
    order_date: date
    notes: str | None = None
    items: list[PurchaseOrderItemRequest] = Field(min_length=1)


class PurchaseOrderItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    quantity_ordered: float
    quantity_received: float
    unit_cost: float

    model_config = {"from_attributes": True}


class PurchaseOrderResponse(BaseModel):
    id: uuid.UUID
    po_number: str
    supplier_id: uuid.UUID
    order_date: date
    status: str
    items: list[PurchaseOrderItemResponse]

    model_config = {"from_attributes": True}


class GoodsReceiptItemRequest(BaseModel):
    product_id: uuid.UUID
    quantity: float = Field(gt=0)
    # Bonus/free pieces included within `quantity` (e.g. a supplier's
    # "10+1 free" scheme) -- physically received and sellable, but not
    # part of what's owed to the supplier. Must be <= quantity.
    free_quantity: float = Field(ge=0, default=0)
    unit_cost: float = Field(ge=0)
    batch_number: str | None = None
    expiry_date: date | None = None

    @model_validator(mode="after")
    def _free_quantity_within_total(self) -> "GoodsReceiptItemRequest":
        if self.free_quantity > self.quantity:
            raise ValueError("free_quantity cannot exceed quantity")
        return self


class GoodsReceiptCreateRequest(BaseModel):
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID
    purchase_order_id: uuid.UUID | None = None
    supplier_invoice_number: str | None = None
    items: list[GoodsReceiptItemRequest] = Field(min_length=1)


class GoodsReceiptItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    batch_id: uuid.UUID | None
    quantity: float
    free_quantity: float
    unit_cost: float

    model_config = {"from_attributes": True}


class GoodsReceiptResponse(BaseModel):
    id: uuid.UUID
    grn_number: str
    supplier_id: uuid.UUID
    received_at: datetime
    items: list[GoodsReceiptItemResponse]

    model_config = {"from_attributes": True}
