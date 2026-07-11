import uuid

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
