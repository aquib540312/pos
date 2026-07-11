from datetime import date, datetime

from pydantic import BaseModel


class GSTR1FilingResponse(BaseModel):
    return_period: str
    period_start: date
    period_end: date
    status: str
    gsp_reference: str | None
    submitted_at: datetime | None
    filed_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}


class GSTR1PayloadResponse(BaseModel):
    return_period: str
    status: str
    payload: dict
