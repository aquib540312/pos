from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationError
from app.models.organization import Branch
from app.models.rbac import User
from app.models.subscriptions import Plan, Subscription
from app.modules.subscriptions.adapters import SubscriptionGatewayAdapter, get_subscription_adapter
from app.modules.subscriptions.repository import PlanRepository, SubscriptionRepository

# Events that mean "the subscription is in good standing, keep serving
# this tenant" -- fired on the first successful mandate charge and on
# every successful renewal.
_ACTIVE_EVENTS = {"subscription.activated", "subscription.charged"}
# Payment retries have been exhausted (or a renewal is stuck retrying) --
# the tenant keeps their data but core/deps locks out write access until
# they fix payment.
_PAST_DUE_EVENTS = {"subscription.pending", "subscription.halted"}
_CANCELED_EVENTS = {"subscription.cancelled", "subscription.completed"}

# Statuses that keep an org's requests flowing through core/deps'
# subscription gate. Deliberately does NOT include "past_due"/"canceled" --
# see SubscriptionService.is_locked_out.
_GOOD_STANDING = {"trialing", "active"}


class SubscriptionService:
    def __init__(self, db: Session, settings: Settings | None = None, adapter: SubscriptionGatewayAdapter | None = None):
        self.db = db
        self.settings = settings or get_settings()
        self.subscriptions = SubscriptionRepository(db)
        self.plans = PlanRepository(db)
        self.adapter: SubscriptionGatewayAdapter = adapter or get_subscription_adapter(self.settings)

    def get_plan_or_404(self, code: str) -> Plan:
        plan = self.plans.get_by_code(code)
        if plan is None:
            raise NotFoundError(f"Plan '{code}' not found")
        return plan

    def start_trial(self, organization_id: uuid.UUID, plan_code: str) -> Subscription:
        plan = self.get_plan_or_404(plan_code)
        subscription = Subscription(
            organization_id=organization_id,
            plan_id=plan.id,
            status="trialing",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=self.settings.trial_period_days),
        )
        return self.subscriptions.add(subscription)

    def _usage(self, organization_id: uuid.UUID) -> tuple[int, int]:
        branches_used = self.db.execute(
            select(func.count()).select_from(Branch).where(Branch.organization_id == organization_id)
        ).scalar_one()
        users_used = self.db.execute(
            select(func.count()).select_from(User).where(User.organization_id == organization_id)
        ).scalar_one()
        return branches_used, users_used

    def get_for_org(self, organization_id: uuid.UUID) -> tuple[Subscription, int, int]:
        subscription = self.subscriptions.get_by_org(organization_id)
        if subscription is None:
            raise NotFoundError(f"No subscription for organization {organization_id}")
        branches_used, users_used = self._usage(organization_id)
        return subscription, branches_used, users_used

    def is_locked_out(self, organization_id: uuid.UUID) -> bool:
        """Used by core/deps' request gate. A missing Subscription row
        (any org seeded before this feature existed, or seeded by
        app/seed.py/tests) is treated as unrestricted/grandfathered --
        only an org that HAS a subscription and has let it lapse is
        locked out."""
        subscription = self.subscriptions.get_by_org(organization_id)
        if subscription is None:
            return False
        if subscription.status == "trialing":
            trial_ends_at = subscription.trial_ends_at
            if trial_ends_at is not None and trial_ends_at.tzinfo is None:
                trial_ends_at = trial_ends_at.replace(tzinfo=timezone.utc)
            if trial_ends_at is None or datetime.now(timezone.utc) < trial_ends_at:
                return False
            # Trial ran out with no payment method on file -- lock out
            # lazily on the next request rather than needing a cron job.
            subscription.status = "past_due"
            self.db.flush()
            return True
        return subscription.status not in _GOOD_STANDING

    def start_checkout(self, organization_id: uuid.UUID, plan_code: str) -> tuple[str, str]:
        plan = self.get_plan_or_404(plan_code)
        if self.settings.subscription_provider == "razorpay" and not plan.razorpay_plan_id:
            raise ValidationError(f"Plan '{plan_code}' has no razorpay_plan_id configured")

        subscription = self.subscriptions.get_by_org(organization_id)
        if subscription is None:
            raise NotFoundError(f"No subscription for organization {organization_id}")

        result = self.adapter.create_subscription(
            razorpay_plan_id=plan.razorpay_plan_id or plan.code, total_count=120
        )
        subscription.plan_id = plan.id
        subscription.razorpay_subscription_id = result.gateway_subscription_id
        # The mock adapter simulates an instantly-successful hosted
        # checkout (no webhook will ever arrive in dev/CI to do this) --
        # a real Razorpay checkout instead waits for the
        # subscription.activated webhook (see handle_webhook).
        if self.settings.subscription_provider != "razorpay":
            subscription.status = "active"
            subscription.current_period_end = datetime.now(timezone.utc) + timedelta(days=30)
        self.db.flush()
        return result.checkout_url, result.gateway_subscription_id

    def cancel(self, organization_id: uuid.UUID) -> Subscription:
        subscription = self.subscriptions.get_by_org(organization_id)
        if subscription is None:
            raise NotFoundError(f"No subscription for organization {organization_id}")
        if subscription.status == "canceled":
            raise ConflictError("Subscription is already canceled")
        if subscription.razorpay_subscription_id:
            self.adapter.cancel_subscription(subscription.razorpay_subscription_id)
        subscription.status = "canceled"
        self.db.flush()
        return subscription

    def handle_webhook(self, raw_body: bytes, signature: str) -> Subscription | None:
        if not self.adapter.verify_webhook_signature(raw_body, signature):
            raise AuthenticationError("Invalid Razorpay webhook signature")

        payload = json.loads(raw_body)
        event = payload.get("event")
        if event not in _ACTIVE_EVENTS | _PAST_DUE_EVENTS | _CANCELED_EVENTS:
            return None

        entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
        gateway_subscription_id = entity.get("id")
        if not gateway_subscription_id:
            return None

        subscription = self.subscriptions.get_by_gateway_id(gateway_subscription_id)
        if subscription is None:
            return None

        if event in _ACTIVE_EVENTS:
            subscription.status = "active"
            current_end = entity.get("current_end")
            if current_end:
                subscription.current_period_end = datetime.fromtimestamp(current_end, tz=timezone.utc)
        elif event in _PAST_DUE_EVENTS:
            subscription.status = "past_due"
        elif event in _CANCELED_EVENTS:
            subscription.status = "canceled"
        self.db.flush()
        return subscription
