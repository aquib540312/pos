import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateUpiQrRequest(BaseModel):
    amount: float = Field(gt=0)
    receipt_reference: str = Field(min_length=1, max_length=60)


class PaymentGatewayTransactionResponse(BaseModel):
    id: uuid.UUID
    provider: str
    gateway_reference: str
    amount: float
    status: str
    receipt_reference: str | None
    qr_image_url: str | None
    paid_at: datetime | None

    model_config = {"from_attributes": True}
