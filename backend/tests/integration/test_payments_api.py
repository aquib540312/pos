import hashlib
import hmac
import json

from app.core.config import get_settings
from app.modules.payments.adapters import QRCodeResult


def _sign(body: bytes) -> str:
    secret = get_settings().razorpay_webhook_secret
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_create_upi_qr_stores_transaction(client, seeded_org, monkeypatch):
    # The actual Razorpay network call is the one thing we can't exercise
    # without live credentials -- mock only that boundary, everything
    # else (persistence, response shape, permission gate) is real.
    monkeypatch.setattr(
        "app.modules.payments.adapters.RazorpayAdapter.create_upi_qr",
        lambda self, amount_rupees, receipt_reference: QRCodeResult(
            gateway_reference="qr_fake123", image_url="https://rzp.io/i/fake.png", close_by=9999999999
        ),
    )

    resp = client.post(
        "/api/v1/payments/razorpay/qr",
        headers=seeded_org["auth_headers"],
        json={"amount": 236.0, "receipt_reference": "INV/2026/000001"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "created"
    assert body["gateway_reference"] == "qr_fake123"
    assert body["amount"] == 236.0


def test_webhook_marks_transaction_paid(client, seeded_org, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.modules.payments.adapters.RazorpayAdapter.create_upi_qr",
        lambda self, amount_rupees, receipt_reference: QRCodeResult(
            gateway_reference="qr_webhook_test", image_url="https://rzp.io/i/fake.png", close_by=9999999999
        ),
    )
    create_resp = client.post(
        "/api/v1/payments/razorpay/qr",
        headers=seeded_org["auth_headers"],
        json={"amount": 100.0, "receipt_reference": "INV/2026/000002"},
    )
    transaction_id = create_resp.json()["id"]

    webhook_payload = {
        "entity": "event",
        "event": "qr_code.credited",
        "contains": ["qr_code", "payment"],
        "payload": {
            "qr_code": {"entity": {"id": "qr_webhook_test", "entity": "qr_code"}},
            "payment": {"entity": {"id": "pay_fake456", "entity": "payment", "amount": 10000}},
        },
        "created_at": 1700000000,
    }
    raw_body = json.dumps(webhook_payload).encode()
    signature = _sign(raw_body)

    webhook_resp = client.post(
        "/api/v1/payments/razorpay/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
    )
    assert webhook_resp.status_code == 200, webhook_resp.text

    status_resp = client.get(f"/api/v1/payments/razorpay/qr/{transaction_id}", headers=seeded_org["auth_headers"])
    assert status_resp.json()["status"] == "paid"


def test_webhook_rejects_invalid_signature(client, seeded_org):
    raw_body = json.dumps({"event": "qr_code.credited", "payload": {}}).encode()
    resp = client.post(
        "/api/v1/payments/razorpay/webhook",
        content=raw_body,
        headers={"X-Razorpay-Signature": "not-a-real-signature", "Content-Type": "application/json"},
    )
    assert resp.status_code == 400


def test_unknown_qr_transaction_status_is_404(client, seeded_org):
    import uuid

    resp = client.get(f"/api/v1/payments/razorpay/qr/{uuid.uuid4()}", headers=seeded_org["auth_headers"])
    assert resp.status_code == 404
