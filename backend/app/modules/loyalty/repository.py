from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.loyalty import Coupon, GiftCard, GiftCardTransaction


class CouponRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_code(self, organization_id: uuid.UUID, code: str) -> Coupon | None:
        stmt = select(Coupon).where(Coupon.organization_id == organization_id, Coupon.code == code)
        return self.db.execute(stmt).scalars().first()

    def get(self, coupon_id: uuid.UUID) -> Coupon | None:
        return self.db.get(Coupon, coupon_id)

    def list(self, organization_id: uuid.UUID) -> list[Coupon]:
        return list(self.db.execute(select(Coupon).where(Coupon.organization_id == organization_id)).scalars())

    def add(self, coupon: Coupon) -> Coupon:
        self.db.add(coupon)
        self.db.flush()
        return coupon


class GiftCardRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_number(self, organization_id: uuid.UUID, card_number: str) -> GiftCard | None:
        stmt = select(GiftCard).where(GiftCard.organization_id == organization_id, GiftCard.card_number == card_number)
        return self.db.execute(stmt).scalars().first()

    def get(self, card_id: uuid.UUID) -> GiftCard | None:
        return self.db.get(GiftCard, card_id)

    def list(self, organization_id: uuid.UUID) -> list[GiftCard]:
        return list(
            self.db.execute(select(GiftCard).where(GiftCard.organization_id == organization_id)).scalars()
        )

    def add(self, gift_card: GiftCard) -> GiftCard:
        self.db.add(gift_card)
        self.db.flush()
        return gift_card

    def add_transaction(self, transaction: GiftCardTransaction) -> GiftCardTransaction:
        self.db.add(transaction)
        self.db.flush()
        return transaction
