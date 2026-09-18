import uuid
from datetime import datetime
from pydantic import BaseModel, Field

WASTE_REASONS = ["spoilage", "expired", "damaged", "cutting_loss", "bone_loss", "processing_loss", "other"]

class WasteCreateRequest(BaseModel):
    product_id: uuid.UUID
    quantity: float = Field(gt=0)
    unit_cost: float = Field(ge=0)
    reason: str = Field(pattern="^(spoilage|expired|damaged|cutting_loss|bone_loss|processing_loss|other)$")
    notes: str | None = Field(default=None, max_length=500)

class WasteResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    quantity: float
    unit_cost: float
    total_cost: float
    reason: str
    notes: str | None
    recorded_by: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}
