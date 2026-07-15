"""Recurring billing adapter -- Razorpay Subscriptions API.

Real, documented contract (https://razorpay.com/docs/api/payments/subscriptions/):
  POST /v1/subscriptions   create a subscription against a Razorpay-side
                           plan_id (created once via dashboard/API and
                           stored on our Plan.razorpay_plan_id); the
                           response includes `short_url`, a hosted page
                           where the customer authorizes the mandate and
                           pays the first cycle -- no checkout.js/frontend
                           SDK needed, just redirect there.
  POST /v1/subscriptions/{id}/cancel
  Webhook events "subscription.activated" / "subscription.charged" /
  "subscription.halted" / "subscription.cancelled" fire on lifecycle
  changes, signed the same way as the existing UPI QR webhook (HMAC-SHA256
  over the raw body, X-Razorpay-Signature header).

Swapping in a real merchant account is a config change only
(POS_SUBSCRIPTION_PROVIDER=razorpay + real razorpay_key_id/secret + each
Plan's razorpay_plan_id) -- nothing in this module's callers changes.

MockSubscriptionAdapter is the default so signup -> trial -> subscribe ->
renew is fully exercisable end-to-end without a live Razorpay account
(same reasoning as gst_filing/adapters.py's MockGSPAdapter): checkout
"succeeds" immediately with a reproducible reference.
"""

from dataclasses import dataclass
from typing import Protocol

import razorpay

from app.core.config import Settings


@dataclass(frozen=True)
class SubscriptionCheckoutResult:
    gateway_subscription_id: str
    checkout_url: str


class SubscriptionGatewayAdapter(Protocol):
    def create_subscription(self, razorpay_plan_id: str, total_count: int) -> SubscriptionCheckoutResult: ...
    def cancel_subscription(self, gateway_subscription_id: str) -> None: ...
    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool: ...


class MockSubscriptionAdapter:
    def create_subscription(self, razorpay_plan_id: str, total_count: int) -> SubscriptionCheckoutResult:
        return SubscriptionCheckoutResult(
            gateway_subscription_id=f"MOCKSUB-{razorpay_plan_id}",
            checkout_url="#mock-checkout-already-active",
        )

    def cancel_subscription(self, gateway_subscription_id: str) -> None:
        pass

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        return True


class RazorpayAdapter:
    def __init__(self, settings: Settings):
        self._client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
        self._webhook_secret = settings.razorpay_webhook_secret

    def create_subscription(self, razorpay_plan_id: str, total_count: int) -> SubscriptionCheckoutResult:
        # total_count is the number of billing cycles Razorpay will run
        # before the mandate needs re-authorization -- 120 monthly cycles
        # (10 years) is effectively "until canceled" for a monthly plan.
        response = self._client.subscription.create(
            {"plan_id": razorpay_plan_id, "customer_notify": 1, "total_count": total_count}
        )
        return SubscriptionCheckoutResult(
            gateway_subscription_id=response["id"], checkout_url=response["short_url"]
        )

    def cancel_subscription(self, gateway_subscription_id: str) -> None:
        self._client.subscription.cancel(gateway_subscription_id)

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        try:
            self._client.utility.verify_webhook_signature(raw_body.decode(), signature, self._webhook_secret)
            return True
        except razorpay.errors.SignatureVerificationError:
            return False


def get_subscription_adapter(settings: Settings) -> SubscriptionGatewayAdapter:
    if settings.subscription_provider == "razorpay":
        return RazorpayAdapter(settings)
    return MockSubscriptionAdapter()
