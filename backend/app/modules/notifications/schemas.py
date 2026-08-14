import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SendNotificationRequest(BaseModel):
    channel: str = Field(pattern="^(sms|whatsapp|email)$")
    to: str
    message: str


class AppNotificationResponse(BaseModel):
    id: uuid.UUID
    category: str
    title: str
    body: str | None
    reference_type: str | None
    reference_id: uuid.UUID | None
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UnreadCountResponse(BaseModel):
    unread_count: int
