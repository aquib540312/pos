import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PlanResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    price_monthly: float
    max_branches: int | None
    max_users: int | None

    model_config = {"from_attributes": True}


class SubscriptionResponse(BaseModel):
    id: uuid.UUID
    plan: PlanResponse
    status: str
    trial_ends_at: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool
    branches_used: int
    users_used: int

    model_config = {"from_attributes": True}


class CheckoutRequest(BaseModel):
    plan_code: str = Field(pattern="^(starter|growth|enterprise)$")


class CheckoutResponse(BaseModel):
    checkout_url: str
    gateway_subscription_id: str
