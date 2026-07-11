import uuid

from pydantic import BaseModel, Field


class ShiftOpenRequest(BaseModel):
    branch_id: uuid.UUID
    opening_cash: float = Field(ge=0)


class ShiftCloseRequest(BaseModel):
    counted_closing_cash: float = Field(ge=0)


class ShiftResponse(BaseModel):
    id: uuid.UUID
    branch_id: uuid.UUID
    user_id: uuid.UUID
    opening_cash: float
    expected_closing_cash: float | None
    counted_closing_cash: float | None
    cash_variance: float | None
    status: str

    model_config = {"from_attributes": True}
