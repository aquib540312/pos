import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class StockItemResponse(BaseModel):
    warehouse_id: uuid.UUID
    product_id: uuid.UUID
    batch_id: uuid.UUID | None
    quantity_on_hand: float

    model_config = {"from_attributes": True}


class StockAdjustmentRequest(BaseModel):
    warehouse_id: uuid.UUID
    product_id: uuid.UUID
    batch_id: uuid.UUID | None = None
    quantity_delta: float = Field(description="Positive to add stock, negative to remove")
    reason: str = Field(min_length=1, max_length=255)


class StockTransferItemRequest(BaseModel):
    product_id: uuid.UUID
    batch_id: uuid.UUID | None = None
    quantity: float = Field(gt=0)


class StockTransferCreateRequest(BaseModel):
    source_warehouse_id: uuid.UUID
    destination_warehouse_id: uuid.UUID
    items: list[StockTransferItemRequest] = Field(min_length=1)


class StockTransferItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    batch_id: uuid.UUID | None
    quantity: float

    model_config = {"from_attributes": True}


class StockTransferResponse(BaseModel):
    id: uuid.UUID
    transfer_number: str
    source_warehouse_id: uuid.UUID
    destination_warehouse_id: uuid.UUID
    status: str
    dispatched_at: datetime | None = None
    received_at: datetime | None = None
    items: list[StockTransferItemResponse]

    model_config = {"from_attributes": True}
