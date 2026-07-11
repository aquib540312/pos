import hashlib
import hmac

from app.core.config import Settings
from app.modules.payments.adapters import RazorpayAdapter


def _settings():
    return Settings(razorpay_key_id="rzp_test_x", razorpay_key_secret="x", razorpay_webhook_secret="whsec_test123")


def _sign(body: bytes, secret: str) -> str:
    # Mirrors Razorpay's own documented algorithm exactly (HMAC-SHA256 hex
    # digest of the raw body) -- this is what we're verifying our adapter
    # correctly delegates to the official SDK for, not reimplementing.
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_is_accepted():
    adapter = RazorpayAdapter(_settings())
    body = b'{"event": "payment.captured"}'
    signature = _sign(body, "whsec_test123")
    assert adapter.verify_webhook_signature(body, signature) is True


def test_tampered_body_is_rejected():
    adapter = RazorpayAdapter(_settings())
    body = b'{"event": "payment.captured"}'
    signature = _sign(body, "whsec_test123")
    tampered_body = b'{"event": "payment.captured", "amount": 999999}'
    assert adapter.verify_webhook_signature(tampered_body, signature) is False


def test_wrong_secret_is_rejected():
    adapter = RazorpayAdapter(_settings())
    body = b'{"event": "payment.captured"}'
    signature = _sign(body, "wrong-secret")
    assert adapter.verify_webhook_signature(body, signature) is False


def test_missing_signature_is_rejected():
    adapter = RazorpayAdapter(_settings())
    body = b'{"event": "payment.captured"}'
    assert adapter.verify_webhook_signature(body, "") is False
