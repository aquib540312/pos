import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.modules.sales.schemas import PaymentRequest, SaleLineRequest


class TerminalRegisterRequest(BaseModel):
    branch_id: uuid.UUID
    name: str = Field(min_length=1, max_length=120)
    device_fingerprint: str = Field(min_length=1, max_length=200)


class TerminalRegisterResponse(BaseModel):
    id: uuid.UUID
    name: str
    branch_id: uuid.UUID
    api_key: str

    model_config = {"from_attributes": True}


class OfflineSalePayload(BaseModel):
    """A sale rung up while offline, as queued locally by `sync_agent`.
    Deliberately narrower than `SaleCreateRequest` -- gift cards and UPI QR
    payments need the network at the moment of sale, so they can't have
    been used offline in the first place."""

    client_operation_id: str = Field(min_length=1, max_length=64)
    occurred_at: datetime
    branch_id: uuid.UUID
    warehouse_id: uuid.UUID
    customer_id: uuid.UUID | None = None
    items: list[SaleLineRequest] = Field(min_length=1)
    payments: list[PaymentRequest] = Field(default_factory=list)
    is_credit_sale: bool = False
    coupon_code: str | None = None


class PushRequest(BaseModel):
    offline_sales: list[OfflineSalePayload] = Field(default_factory=list)


class OfflineSaleResult(BaseModel):
    client_operation_id: str
    status: Literal["applied", "conflict", "rejected"]
    invoice_id: uuid.UUID | None = None
    conflict_id: uuid.UUID | None = None
    error_detail: str | None = None


class PushResponse(BaseModel):
    results: list[OfflineSaleResult]


class ChangeLogEntryResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: uuid.UUID
    operation: str
    payload: dict[str, Any]
    created_at: datetime


class PullResponse(BaseModel):
    changes: list[ChangeLogEntryResponse]
    next_cursor: int
    has_more: bool


class ConflictResponse(BaseModel):
    id: uuid.UUID
    terminal_id: uuid.UUID
    offline_sale_id: uuid.UUID | None
    conflict_type: str
    details: dict[str, Any]
    status: str
    resolution: str | None
    resolution_notes: str | None
    created_at: datetime
    resolved_at: datetime | None


class ConflictResolveRequest(BaseModel):
    resolution: Literal["retry", "cancel"]
    notes: str | None = Field(default=None, max_length=500)


class TerminalStatusResponse(BaseModel):
    id: uuid.UUID
    name: str
    branch_id: uuid.UUID
    is_active: bool
    last_seen_at: datetime | None

    model_config = {"from_attributes": True}


class SyncStatusResponse(BaseModel):
    terminals: list[TerminalStatusResponse]
    open_conflicts: int
    latest_change_log_id: int
