import uuid
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.loyalty import Coupon, GiftCard, GiftCardTransaction, LoyaltyTransaction
from app.models.party import Customer
from app.modules.loyalty.repository import CouponRepository, GiftCardRepository

POINTS_PER_RUPEE_SPENT = 0.01  # 1 point per Rs.100 taxable spend
POINT_VALUE_IN_RUPEES = 1.0  # 1 point = Re.1 discount on redemption


class LoyaltyService:
    def __init__(self, db: Session):
        self.db = db

    def points_earned_for_amount(self, taxable_amount: float) -> float:
        return round(taxable_amount * POINTS_PER_RUPEE_SPENT, 2)

    def earn(self, customer: Customer, invoice_id: uuid.UUID, taxable_amount: float) -> float:
        points = self.points_earned_for_amount(taxable_amount)
        if points <= 0:
            return 0.0
        customer.loyalty_points_balance = float(customer.loyalty_points_balance) + points
        self.db.add(
            LoyaltyTransaction(
                organization_id=customer.organization_id,
                customer_id=customer.id,
                invoice_id=invoice_id,
                points_delta=points,
                reason="earn",
                created_at=datetime.now(timezone.utc),
            )
        )
        self.db.flush()
        return points

    def redeem(self, customer: Customer, invoice_id: uuid.UUID, points: float) -> float:
        """Returns the rupee discount value of the redeemed points."""
        if points <= 0:
            return 0.0
        if points > float(customer.loyalty_points_balance):
            raise ValidationError(
                f"Customer has {customer.loyalty_points_balance} points, cannot redeem {points}"
            )
        customer.loyalty_points_balance = float(customer.loyalty_points_balance) - points
        self.db.add(
            LoyaltyTransaction(
                organization_id=customer.organization_id,
                customer_id=customer.id,
                invoice_id=invoice_id,
                points_delta=-points,
                reason="redeem",
                created_at=datetime.now(timezone.utc),
            )
        )
        self.db.flush()
        return points * POINT_VALUE_IN_RUPEES


class CouponService:
    def __init__(self, db: Session):
        self.db = db
        self.coupons = CouponRepository(db)

    def create_coupon(self, organization_id: uuid.UUID, **fields) -> Coupon:
        if self.coupons.get_by_code(organization_id, fields["code"]) is not None:
            raise ConflictError(f"Coupon code '{fields['code']}' already exists")
        return self.coupons.add(Coupon(organization_id=organization_id, **fields))

    def validate(self, organization_id: uuid.UUID, code: str, order_value: float) -> tuple[Coupon, float]:
        """Returns the coupon and the discount amount it grants, without
        marking it redeemed -- call `redeem` separately once the sale
        actually completes, so a validated-but-abandoned cart doesn't
        consume a limited-use coupon."""
        coupon = self.coupons.get_by_code(organization_id, code)
        if coupon is None or not coupon.is_active:
            raise NotFoundError(f"Coupon '{code}' not found or inactive")
        today = date.today()
        if coupon.valid_from > today or (coupon.valid_until and coupon.valid_until < today):
            raise ValidationError(f"Coupon '{code}' is not valid today")
        if coupon.max_redemptions is not None and coupon.times_redeemed >= coupon.max_redemptions:
            raise ValidationError(f"Coupon '{code}' has reached its redemption limit")
        if order_value < float(coupon.min_order_value):
            raise ValidationError(f"Order value {order_value} is below coupon minimum {coupon.min_order_value}")

        if coupon.discount_type == "percent":
            discount = round(order_value * float(coupon.discount_value) / 100, 2)
        else:
            discount = min(float(coupon.discount_value), order_value)
        return coupon, discount

    def redeem(self, coupon: Coupon) -> None:
        coupon.times_redeemed += 1
        self.db.flush()


class GiftCardService:
    def __init__(self, db: Session):
        self.db = db
        self.gift_cards = GiftCardRepository(db)

    def issue(self, organization_id: uuid.UUID, **fields) -> GiftCard:
        if self.gift_cards.get_by_number(organization_id, fields["card_number"]) is not None:
            raise ConflictError(f"Gift card '{fields['card_number']}' already exists")
        card = GiftCard(organization_id=organization_id, balance=fields["initial_value"], **fields)
        return self.gift_cards.add(card)

    def redeem(self, organization_id: uuid.UUID, card_number: str, amount: float, invoice_id: uuid.UUID | None) -> float:
        card = self.gift_cards.get_by_number(organization_id, card_number)
        if card is None or not card.is_active:
            raise NotFoundError(f"Gift card '{card_number}' not found or inactive")
        if card.expires_on and card.expires_on < date.today():
            raise ValidationError(f"Gift card '{card_number}' has expired")
        if amount > float(card.balance):
            raise ValidationError(f"Gift card balance {card.balance} is less than requested {amount}")
        card.balance = float(card.balance) - amount
        self.gift_cards.add_transaction(
            GiftCardTransaction(
                gift_card_id=card.id,
                invoice_id=invoice_id,
                amount_delta=-amount,
                created_at=datetime.now(timezone.utc),
            )
        )
        self.db.flush()
        return amount
