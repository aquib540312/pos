import uuid
from datetime import date

from pydantic import BaseModel, Field, model_validator


class AccountResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    account_type: str
    is_system: bool

    model_config = {"from_attributes": True}


class TrialBalanceLine(BaseModel):
    account_id: uuid.UUID
    account_code: str
    account_name: str
    account_type: str
    debit_balance: float
    credit_balance: float


class TrialBalanceResponse(BaseModel):
    as_of: date
    lines: list[TrialBalanceLine]
    total_debit: float
    total_credit: float


class AccountLedgerLine(BaseModel):
    entry_id: uuid.UUID
    entry_date: date
    reference_type: str
    narration: str | None
    debit: float
    credit: float
    running_balance: float


class LedgerResponse(BaseModel):
    account_id: uuid.UUID
    account_code: str
    account_name: str
    start: date | None
    end: date | None
    opening_balance: float
    lines: list[AccountLedgerLine]
    closing_balance: float


class JournalLineRequest(BaseModel):
    account_code: str = Field(min_length=1, max_length=20)
    debit: float = Field(ge=0, default=0)
    credit: float = Field(ge=0, default=0)


class ManualJournalRequest(BaseModel):
    entry_date: date
    narration: str | None = None
    lines: list[JournalLineRequest] = Field(min_length=2)

    @model_validator(mode="after")
    def _balances(self) -> "ManualJournalRequest":
        total_debit = sum(line.debit for line in self.lines)
        total_credit = sum(line.credit for line in self.lines)
        if abs(total_debit - total_credit) > 0.01:
            raise ValueError(f"Journal must balance: debits {total_debit} != credits {total_credit}")
        if total_debit <= 0:
            raise ValueError("Journal entry cannot be all zeros")
        for line in self.lines:
            if line.debit > 0 and line.credit > 0:
                raise ValueError("A journal line cannot be both a debit and a credit")
        return self


class JournalEntryResponse(BaseModel):
    id: uuid.UUID
    entry_date: date
    reference_type: str
    reference_id: uuid.UUID | None
    narration: str | None
    lines: list[dict]

    model_config = {"from_attributes": True}


class ExpenseCreateRequest(BaseModel):
    entry_date: date
    amount: float = Field(gt=0)
    account_code: str = Field(min_length=1, max_length=20)
    method: str = Field(default="cash", pattern="^(cash|bank|card|upi)$")
    reference: str | None = None
    narration: str | None = Field(default=None, max_length=255)


class ExpenseResponse(BaseModel):
    id: uuid.UUID
    entry_date: date
    amount: float
    account_code: str
    account_name: str
    method: str
    reference: str | None
    narration: str | None

    model_config = {"from_attributes": True}
