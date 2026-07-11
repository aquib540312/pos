import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.payments.schemas import CreateUpiQrRequest, PaymentGatewayTransactionResponse
from app.modules.payments.service import PaymentGatewayService

router = APIRouter(prefix="/api/v1/payments", tags=["payments"])


@router.post("/razorpay/qr", response_model=PaymentGatewayTransactionResponse, status_code=status.HTTP_201_CREATED)
def create_upi_qr(
    payload: CreateUpiQrRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SALES_CREATE)),
):
    service = PaymentGatewayService(db)
    transaction = service.create_upi_qr(user.organization_id, payload.amount, payload.receipt_reference)
    db.commit()
    return transaction


@router.get("/razorpay/qr/{transaction_id}", response_model=PaymentGatewayTransactionResponse)
def get_upi_qr_status(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SALES_CREATE)),
):
    try:
        return PaymentGatewayService(db).get_status(transaction_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/razorpay/qr/{transaction_id}/cancel", response_model=PaymentGatewayTransactionResponse)
def cancel_upi_qr(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SALES_CREATE)),
):
    try:
        transaction = PaymentGatewayService(db).cancel(transaction_id)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return transaction


@router.post("/razorpay/webhook", status_code=status.HTTP_200_OK)
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    """Razorpay calls this directly (no JWT -- it's not our user), so the
    only trust boundary is the HMAC signature over the *raw* request body.
    Must read the body as raw bytes, not a parsed model, since Razorpay
    signs the exact bytes it sent and re-serializing would break the
    signature check on any whitespace/key-order difference."""
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    try:
        PaymentGatewayService(db).handle_webhook(raw_body, signature)
        db.commit()
    except AuthenticationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"status": "ok"}
