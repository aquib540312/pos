"""Payment gateway adapter -- Razorpay UPI QR Code API.

Real, documented contract (https://razorpay.com/docs/api/payments/qr-codes/):
  POST   /v1/payments/qr_codes            create a dynamic UPI QR
  POST   /v1/payments/qr_codes/{id}/close  close it early
  Webhook events "qr_code.credited" / "payment.captured" fire on payment,
  signed with HMAC-SHA256 over the raw body using the webhook secret
  (X-Razorpay-Signature header) -- verified via the official SDK's
  `utility.verify_webhook_signature`, not reimplemented here, so we never
  drift from Razorpay's own algorithm.

Swapping in a real merchant account is a config change only: set
POS_RAZORPAY_KEY_ID / POS_RAZORPAY_KEY_SECRET / POS_RAZORPAY_WEBHOOK_SECRET
to the live values from https://dashboard.razorpay.com/app/keys and
https://dashboard.razorpay.com/app/webhooks. Nothing in this module or its
callers needs to change.
"""

import time
from dataclasses import dataclass
from typing import Protocol

import razorpay

from app.core.config import Settings


@dataclass(frozen=True)
class QRCodeResult:
    gateway_reference: str
    image_url: str
    close_by: int


class PaymentGatewayAdapter(Protocol):
    def create_upi_qr(self, amount_rupees: float, receipt_reference: str) -> QRCodeResult: ...
    def close_qr(self, gateway_reference: str) -> None: ...
    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool: ...


class RazorpayAdapter:
    def __init__(self, settings: Settings):
        self._client = razorpay.Client(auth=(settings.razorpay_key_id, settings.razorpay_key_secret))
        self._webhook_secret = settings.razorpay_webhook_secret
        self._expiry_seconds = settings.razorpay_qr_expiry_minutes * 60

    def create_upi_qr(self, amount_rupees: float, receipt_reference: str) -> QRCodeResult:
        # Razorpay amounts are always in paise (smallest currency unit).
        response = self._client.qrcode.create(
            {
                "type": "upi_qr",
                "name": "POS Sale",
                "usage": "single_use",
                "fixed_amount": True,
                "payment_amount": round(amount_rupees * 100),
                "description": receipt_reference,
                "close_by": int(time.time()) + self._expiry_seconds,
                "notes": {"receipt_reference": receipt_reference},
            }
        )
        return QRCodeResult(
            gateway_reference=response["id"],
            image_url=response["image_url"],
            close_by=response["close_by"],
        )

    def close_qr(self, gateway_reference: str) -> None:
        self._client.qrcode.close(gateway_reference)

    def verify_webhook_signature(self, raw_body: bytes, signature: str) -> bool:
        try:
            self._client.utility.verify_webhook_signature(raw_body.decode(), signature, self._webhook_secret)
            return True
        except razorpay.errors.SignatureVerificationError:
            return False
