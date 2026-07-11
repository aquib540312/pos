from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.loyalty.schemas import (
    CouponCreateRequest,
    CouponResponse,
    CouponValidateRequest,
    CouponValidateResponse,
    GiftCardIssueRequest,
    GiftCardRedeemRequest,
    GiftCardResponse,
)
from app.modules.loyalty.service import CouponService, GiftCardService

router = APIRouter(prefix="/api/v1/loyalty", tags=["loyalty"])


@router.post("/coupons", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
def create_coupon(
    payload: CouponCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    try:
        coupon = CouponService(db).create_coupon(user.organization_id, **payload.model_dump())
        db.commit()
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return coupon


@router.post("/coupons/validate", response_model=CouponValidateResponse)
def validate_coupon(
    payload: CouponValidateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SALES_CREATE)),
):
    try:
        _, discount = CouponService(db).validate(user.organization_id, payload.code, payload.order_value)
    except (NotFoundError, ValidationError) as exc:
        return CouponValidateResponse(valid=False, discount_amount=0, reason=str(exc))
    return CouponValidateResponse(valid=True, discount_amount=discount)


@router.post("/gift-cards", response_model=GiftCardResponse, status_code=status.HTTP_201_CREATED)
def issue_gift_card(
    payload: GiftCardIssueRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.CATALOG_MANAGE)),
):
    try:
        card = GiftCardService(db).issue(user.organization_id, **payload.model_dump())
        db.commit()
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return card


@router.post("/gift-cards/redeem", response_model=GiftCardResponse)
def redeem_gift_card(
    payload: GiftCardRedeemRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.SALES_CREATE)),
):
    service = GiftCardService(db)
    try:
        service.redeem(user.organization_id, payload.card_number, payload.amount, payload.invoice_id)
        db.commit()
    except (NotFoundError, ValidationError) as exc:
        db.rollback()
        code = status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(code, str(exc)) from exc
    return service.gift_cards.get_by_number(user.organization_id, payload.card_number)
