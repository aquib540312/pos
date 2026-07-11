import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import (
    CreditLimitExceededError,
    DomainError,
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.sales.schemas import (
    ReturnCreateRequest,
    ReturnResponse,
    SaleCreateRequest,
    SaleInvoiceResponse,
)
from app.modules.sales.service import SalesService

router = APIRouter(prefix="/api/v1/sales", tags=["sales"])

_ERROR_STATUS = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InsufficientStockError: status.HTTP_409_CONFLICT,
    CreditLimitExceededError: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


def _handle(exc: DomainError, db: Session):
    db.rollback()
    for exc_type, code in _ERROR_STATUS.items():
        if isinstance(exc, exc_type):
            raise HTTPException(code, str(exc)) from exc
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("", response_model=list[SaleInvoiceResponse])
def list_sales(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.REPORTS_VIEW))):
    return SalesService(db).invoices.list(user.organization_id)


@router.get("/{invoice_id}", response_model=SaleInvoiceResponse)
def get_sale(
    invoice_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.REPORTS_VIEW))
):
    invoice = SalesService(db).invoices.get(invoice_id)
    if invoice is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Invoice {invoice_id} not found")
    return invoice


@router.post("", response_model=SaleInvoiceResponse, status_code=status.HTTP_201_CREATED)
def create_sale(
    payload: SaleCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SALES_CREATE)),
):
    service = SalesService(db)
    try:
        invoice = service.create_sale(
            organization_id=user.organization_id,
            branch_id=payload.branch_id,
            warehouse_id=payload.warehouse_id,
            customer_id=payload.customer_id,
            shift_id=payload.shift_id,
            items=[i.model_dump() for i in payload.items],
            payments=[p.model_dump() for p in payload.payments],
            redeem_loyalty_points=payload.redeem_loyalty_points,
            is_credit_sale=payload.is_credit_sale,
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return invoice


@router.post("/returns", response_model=ReturnResponse, status_code=status.HTTP_201_CREATED)
def create_return(
    payload: ReturnCreateRequest,
    warehouse_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SALES_RETURN)),
):
    service = SalesService(db)
    original = service.invoices.get(payload.original_invoice_id)
    if original is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Original invoice not found")
    try:
        sales_return = service.create_return(
            organization_id=user.organization_id,
            branch_id=original.branch_id,
            warehouse_id=warehouse_id,
            original_invoice_id=payload.original_invoice_id,
            reason=payload.reason,
            refund_mode=payload.refund_mode,
            items=[i.model_dump() for i in payload.items],
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return sales_return
