import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class CuttingItemRequest(BaseModel):
    product_id: uuid.UUID
    output_weight: float = Field(gt=0)
    waste_weight: float = Field(ge=0, default=0)

class CuttingOrderCreateRequest(BaseModel):
    source_product_id: uuid.UUID
    input_weight: float = Field(gt=0)
    butcher_name: str | None = Field(default=None, max_length=255)
    items: list[CuttingItemRequest] = Field(min_length=1)
    notes: str | None = Field(default=None, max_length=500)

class CuttingItemResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    output_weight: float
    waste_weight: float
    model_config = {"from_attributes": True}

class CuttingOrderResponse(BaseModel):
    id: uuid.UUID
    source_product_id: uuid.UUID
    source_product_name: str
    input_weight: float
    butcher_name: str | None
    cutting_date: datetime | None
    status: str
    notes: str | None
    items: list[CuttingItemResponse]
    created_at: datetime
    model_config = {"from_attributes": True}
