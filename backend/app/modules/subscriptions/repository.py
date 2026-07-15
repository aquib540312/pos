from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.subscriptions import Plan, Subscription


class PlanRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, plan_id: uuid.UUID) -> Plan | None:
        return self.db.get(Plan, plan_id)

    def get_by_code(self, code: str) -> Plan | None:
        stmt = select(Plan).where(Plan.code == code)
        return self.db.execute(stmt).scalars().first()

    def list_active(self) -> list[Plan]:
        stmt = select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.price_monthly)
        return list(self.db.execute(stmt).scalars())


class SubscriptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, subscription: Subscription) -> Subscription:
        self.db.add(subscription)
        self.db.flush()
        return subscription

    def get_by_org(self, organization_id: uuid.UUID) -> Subscription | None:
        stmt = (
            select(Subscription)
            .where(Subscription.organization_id == organization_id)
            .options(selectinload(Subscription.plan))
        )
        return self.db.execute(stmt).scalars().first()

    def get_by_gateway_id(self, gateway_subscription_id: str) -> Subscription | None:
        stmt = select(Subscription).where(Subscription.razorpay_subscription_id == gateway_subscription_id)
        return self.db.execute(stmt).scalars().first()
