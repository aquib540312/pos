import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class PurchaseOrderItemRequest(BaseModel):
    product_id: uuid.UUID
    quantity_ordered: float = Field(gt=0)
    unit_cost: float = Field(ge=0)
    discount_amount: float = Field(default=0, ge=0)


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
    discount_amount: float

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
    # Purchase-side GST rate for this line (total slab, e.g. 18.00). Taken
    # from the product's configured HSN when omitted; supplying it here
    # allows a GRN line to carry a different rate than the catalog default
    # (e.g. a supplier invoice at a different slab). Snapshot per line.
    tax_rate_percent: float | None = None
    # Per-line discount off the gross received value (quantity * unit_cost)
    # -- reduces the taxable value and the input GST claimed, mirroring a
    # sale-line discount.
    discount_amount: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _free_quantity_within_total(self) -> "GoodsReceiptItemRequest":
        if self.free_quantity > self.quantity:
            raise ValueError("free_quantity cannot exceed quantity")
        paid_qty = self.quantity - self.free_quantity
        if self.discount_amount > paid_qty * self.unit_cost:
            raise ValueError("discount_amount cannot exceed gross paid line value")
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
    discount_amount: float
    hsn_code_id: uuid.UUID | None
    tax_rate_percent: float
    vat_amount: float

    model_config = {"from_attributes": True}


class GoodsReceiptResponse(BaseModel):
    id: uuid.UUID
    grn_number: str
    supplier_id: uuid.UUID
    warehouse_id: uuid.UUID
    purchase_order_id: uuid.UUID | None = None
    received_at: datetime
    supplier_invoice_number: str | None
    items: list[GoodsReceiptItemResponse]

    model_config = {"from_attributes": True}

class PurchaseOrderStatusUpdateRequest(BaseModel):
    status: str = Field(pattern="^(draft|submitted|cancelled|closed)$")


class PendingGRNItem(BaseModel):
    po_id: uuid.UUID
    po_number: str
    supplier_id: uuid.UUID
    order_date: date
    status: str
    product_id: uuid.UUID
    product_name: str
    sku: str
    quantity_ordered: float
    quantity_received: float
    outstanding_quantity: float


class PurchaseReturnItemRequest(BaseModel):
    product_id: uuid.UUID
    quantity: float = Field(gt=0)
    unit_cost: float = Field(ge=0)
    batch_id: uuid.UUID | None = None
    original_grn_item_id: uuid.UUID | None = None


class PurchaseReturnCreateRequest(BaseModel):
    warehouse_id: uuid.UUID
    supplier_id: uuid.UUID
    # Optional link to the original GoodsReceipt (invoice) this return is
    # against. When provided, returned lines can reference the GRN's lines
    # directly (original_grn_item_id) so taxes/discounts reverse exactly as
    # they were received.
    goods_receipt_id: uuid.UUID | None = None
    reason: str | None = None
    items: list[PurchaseReturnItemRequest] = Field(min_length=1)


class PurchaseReturnItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    batch_id: uuid.UUID | None
    quantity: float
    unit_cost: float
    taxable_value: float
    vat_amount: float
    line_total: float

    model_config = {"from_attributes": True}


class PurchaseReturnResponse(BaseModel):
    id: uuid.UUID
    return_number: str
    supplier_id: uuid.UUID
    goods_receipt_id: uuid.UUID | None
    return_date: datetime
    reason: str | None
    return_total: float
    is_debit_note: bool
    items: list[PurchaseReturnItemResponse]

    model_config = {"from_attributes": True}
