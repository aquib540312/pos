import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import NotFoundError, ValidationError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.accounting.schemas import (
    AccountResponse,
    ExpenseCreateRequest,
    ExpenseResponse,
    JournalEntryResponse,
    LedgerResponse,
    ManualJournalRequest,
    TrialBalanceResponse,
)
from app.modules.accounting.service import AccountingService
from app.modules.audit.service import write_audit_log

router = APIRouter(prefix="/api/v1/accounting", tags=["accounting"])


@router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.REPORTS_VIEW))):
    return AccountingService(db).list_accounts(user.organization_id)


@router.get("/trial-balance", response_model=TrialBalanceResponse)
def trial_balance(
    as_of: date = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    return AccountingService(db).trial_balance(user.organization_id, as_of)


@router.get("/accounts/{account_id}/ledger", response_model=LedgerResponse)
def account_ledger(
    account_id: uuid.UUID,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    try:
        return AccountingService(db).account_ledger(user.organization_id, account_id, start, end)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/journal-entries", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
def post_manual_journal(
    payload: ManualJournalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    service = AccountingService(db)
    try:
        entry = service.post_manual_journal(
            user.organization_id, payload.entry_date, payload.narration, [line.model_dump() for line in payload.lines]
        )
        write_audit_log(
            db, user.organization_id, user.id, "accounting.manual_journal", "journal_entry", entry.id,
            {"narration": payload.narration},
        )
        db.commit()
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return JournalEntryResponse(
        id=entry.id, entry_date=entry.entry_date, reference_type=entry.reference_type,
        reference_id=entry.reference_id, narration=entry.narration,
        lines=[
            {
                "account_code": line.account.code,
                "debit": float(line.debit),
                "credit": float(line.credit),
            }
            for line in entry.lines
            if line.account is not None
        ],
    )


@router.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def post_expense(
    payload: ExpenseCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    service = AccountingService(db)
    try:
        entry = service.post_expense(
            user.organization_id, payload.entry_date, payload.amount, payload.account_code,
            payload.method, payload.reference, payload.narration,
        )
        account = next(
            (
                line.account
                for line in entry.lines
                if line.account is not None and line.account.code == payload.account_code
            ),
            None,
        )
        write_audit_log(
            db, user.organization_id, user.id, "accounting.expense_posted", "journal_entry", entry.id,
            {"account_code": payload.account_code, "amount": payload.amount, "method": payload.method},
        )
        db.commit()
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return ExpenseResponse(
        id=entry.id, entry_date=entry.entry_date, amount=float(payload.amount),
        account_code=payload.account_code, account_name=account.name if account else payload.account_code,
        method=payload.method, reference=payload.reference, narration=payload.narration,
    )
