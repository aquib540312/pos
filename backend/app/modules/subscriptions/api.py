from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_permission
from app.core.exceptions import AuthenticationError, ConflictError, DomainError, NotFoundError, ValidationError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.subscriptions.repository import PlanRepository
from app.modules.subscriptions.schemas import CheckoutRequest, CheckoutResponse, PlanResponse, SubscriptionResponse
from app.modules.subscriptions.service import SubscriptionService

router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])


def _handle(exc: DomainError):
    if isinstance(exc, NotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    if isinstance(exc, ConflictError):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    if isinstance(exc, ValidationError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/plans", response_model=list[PlanResponse])
def list_plans(db: Session = Depends(get_db)):
    """Public -- used by both the signup page and the tenant billing page,
    neither of which necessarily has an authenticated user yet."""
    return PlanRepository(db).list_active()


@router.get("/me", response_model=SubscriptionResponse)
def get_my_subscription(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        subscription, branches_used, users_used = SubscriptionService(db).get_for_org(user.organization_id)
    except DomainError as exc:
        _handle(exc)
    return SubscriptionResponse(
        id=subscription.id,
        plan=subscription.plan,
        status=subscription.status,
        trial_ends_at=subscription.trial_ends_at,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        branches_used=branches_used,
        users_used=users_used,
    )


@router.post("/checkout", response_model=CheckoutResponse)
def start_checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.ORG_MANAGE)),
):
    try:
        checkout_url, gateway_subscription_id = SubscriptionService(db).start_checkout(
            user.organization_id, payload.plan_code
        )
        db.commit()
    except DomainError as exc:
        db.rollback()
        _handle(exc)
    return CheckoutResponse(checkout_url=checkout_url, gateway_subscription_id=gateway_subscription_id)


@router.post("/cancel", response_model=SubscriptionResponse)
def cancel_subscription(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.ORG_MANAGE)),
):
    try:
        service = SubscriptionService(db)
        subscription = service.cancel(user.organization_id)
        db.commit()
        _, branches_used, users_used = service.get_for_org(user.organization_id)
    except DomainError as exc:
        db.rollback()
        _handle(exc)
    return SubscriptionResponse(
        id=subscription.id,
        plan=subscription.plan,
        status=subscription.status,
        trial_ends_at=subscription.trial_ends_at,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        branches_used=branches_used,
        users_used=users_used,
    )


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)) -> dict[str, str]:
    """Razorpay calls this directly (no JWT), so the HMAC signature over the
    raw body is the only trust boundary -- see payments/api.py's identical
    webhook for why the body must stay raw bytes rather than a parsed model."""
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    try:
        SubscriptionService(db).handle_webhook(raw_body, signature)
        db.commit()
    except AuthenticationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return {"status": "ok"}
