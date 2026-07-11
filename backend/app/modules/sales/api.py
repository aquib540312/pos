import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import (
    ConflictError,
    CreditLimitExceededError,
    DomainError,
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.notifications.tasks import send_notification_task
from app.modules.sales.schemas import (
    ReturnCreateRequest,
    ReturnResponse,
    SaleCreateRequest,
    SaleInvoiceResponse,
)
from app.modules.sales.service import SalesService

router = APIRouter(prefix="/api/v1/sales", tags=["sales"])
logger = logging.getLogger("app.sales")

_ERROR_STATUS = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InsufficientStockError: status.HTTP_409_CONFLICT,
    CreditLimitExceededError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ConflictError: status.HTTP_409_CONFLICT,
}


def _handle(exc: DomainError, db: Session):
    db.rollback()
    for exc_type, code in _ERROR_STATUS.items():
        if isinstance(exc, exc_type):
            raise HTTPException(code, str(exc)) from exc
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


def _dispatch_receipt_sms(service: SalesService, invoice) -> None:
    """Best-effort: a receipt SMS is a side effect of a *successful* sale,
    never part of its transactional integrity, so this runs after commit
    and swallows every failure (no broker running, no customer phone,
    MSG91 down) rather than letting any of them surface as a checkout
    error -- the sale already happened."""
    if not invoice.customer_id:
        return
    try:
        customer = service.customers.get(invoice.customer_id)
        if customer and customer.phone:
            message = f"Invoice {invoice.invoice_number}: Rs.{invoice.grand_total} paid. Thank you for shopping with us!"
            send_notification_task.delay("sms", customer.phone, message)
    except Exception:  # noqa: BLE001 - notification dispatch must never break checkout
        logger.warning("Failed to queue receipt SMS for invoice %s", invoice.id, exc_info=True)


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
            coupon_code=payload.coupon_code,
            gift_card_number=payload.gift_card_number,
            gift_card_amount=payload.gift_card_amount,
            payment_gateway_transaction_id=payload.payment_gateway_transaction_id,
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    _dispatch_receipt_sms(service, invoice)
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
