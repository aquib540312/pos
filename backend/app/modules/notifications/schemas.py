from pydantic import BaseModel, Field


class SendNotificationRequest(BaseModel):
    channel: str = Field(pattern="^(sms|whatsapp|email)$")
    to: str
    message: str
