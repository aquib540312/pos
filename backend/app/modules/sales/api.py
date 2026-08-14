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
from app.modules.audit.service import write_audit_log
from app.modules.notifications.tasks import send_notification_task
from app.modules.sales.schemas import (
    CancelSaleRequest,
    QuotationConvertRequest,
    QuotationCreateRequest,
    QuotationResponse,
    ReturnCreateRequest,
    ReturnDetailResponse,
    ReturnResponse,
    SaleCreateRequest,
    SaleInvoiceResponse,
)
from app.modules.sales.service import QuotationService, SalesService

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


# Quotation routes are declared here, before /{invoice_id} -- FastAPI/
# Starlette matches path routes by declaration order, not by the
# eventual UUID type-coercion of a dynamic segment, so "/quotations"
# would otherwise be captured by /{invoice_id} first and fail UUID
# validation (422) instead of ever reaching these handlers.
@router.get("/quotations", response_model=list[QuotationResponse])
def list_quotations(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.QUOTATION_CREATE))):
    return QuotationService(db).quotations.list(user.organization_id)


@router.get("/quotations/{quotation_id}", response_model=QuotationResponse)
def get_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.QUOTATION_CREATE)),
):
    try:
        return QuotationService(db).get_quotation_or_404(quotation_id)
    except DomainError as exc:
        _handle(exc, db)


@router.post("/quotations", response_model=QuotationResponse, status_code=status.HTTP_201_CREATED)
def create_quotation(
    payload: QuotationCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.QUOTATION_CREATE)),
):
    try:
        quotation = QuotationService(db).create_quotation(
            organization_id=user.organization_id,
            branch_id=payload.branch_id,
            customer_id=payload.customer_id,
            quotation_date=payload.quotation_date,
            valid_until=payload.valid_until,
            items=[i.model_dump() for i in payload.items],
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return quotation


@router.post("/quotations/{quotation_id}/send", response_model=QuotationResponse)
def send_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.QUOTATION_CREATE)),
):
    try:
        quotation = QuotationService(db).mark_sent(quotation_id)
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return quotation


@router.post("/quotations/{quotation_id}/expire", response_model=QuotationResponse)
def expire_quotation(
    quotation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.QUOTATION_CREATE)),
):
    try:
        quotation = QuotationService(db).mark_expired(quotation_id)
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return quotation


@router.post(
    "/quotations/{quotation_id}/convert", response_model=SaleInvoiceResponse, status_code=status.HTTP_201_CREATED
)
def convert_quotation(
    quotation_id: uuid.UUID,
    payload: QuotationConvertRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.QUOTATION_CREATE)),
):
    sales_service = SalesService(db)
    try:
        invoice = QuotationService(db).convert_to_sale(
            sales_service=sales_service,
            organization_id=user.organization_id,
            quotation_id=quotation_id,
            warehouse_id=payload.warehouse_id,
            shift_id=payload.shift_id,
            payments=[p.model_dump() for p in payload.payments],
            is_credit_sale=payload.is_credit_sale,
        )
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    _dispatch_receipt_sms(sales_service, invoice)
    return invoice


@router.get("/returns", response_model=list[ReturnResponse])
def list_returns(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SALES_RETURN)),
):
    return SalesService(db).list_returns(user.organization_id)


@router.get("/returns/{return_id}", response_model=ReturnDetailResponse)
def get_return(
    return_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SALES_RETURN)),
):
    try:
        return SalesService(db).get_return_or_404(return_id)
    except DomainError as exc:
        _handle(exc, db)


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
    if original.status != "posted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a posted invoice can have a return recorded")
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


@router.post("/{invoice_id}/cancel", response_model=SaleInvoiceResponse)
def cancel_sale(
    invoice_id: uuid.UUID,
    payload: CancelSaleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SALES_RETURN)),
):
    service = SalesService(db)
    try:
        invoice = service.cancel_invoice(user.organization_id, invoice_id, payload.reason)
        write_audit_log(db, user.organization_id, user.id, "sales.cancel", "sales_invoice", invoice.id)
        db.commit()
    except DomainError as exc:
        _handle(exc, db)
    return invoice
