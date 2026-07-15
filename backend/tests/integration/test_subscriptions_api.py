import uuid
from datetime import datetime, timedelta, timezone

from app.models.rbac import User
from app.models.subscriptions import PasswordResetToken, Subscription


def _signup_payload(**overrides):
    unique = uuid.uuid4().hex[:8]
    payload = {
        "legal_name": f"Signup Test {unique} Pvt Ltd",
        "trade_name": f"Signup Test {unique}",
        "default_state_code": "27",
        "branch_name": "Main Store",
        "admin_full_name": "Owner Admin",
        "admin_email": f"owner-{unique}@example.com",
        "admin_password": "SignupPass123!",
        "plan_code": "starter",
    }
    payload.update(overrides)
    return payload


def test_signup_creates_org_branch_admin_and_trial_subscription(client, db_session):
    payload = _signup_payload()
    resp = client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == payload["admin_email"]

    sub_resp = client.get("/api/v1/subscriptions/me", headers={"Authorization": f"Bearer {token}"})
    assert sub_resp.status_code == 200, sub_resp.text
    body = sub_resp.json()
    assert body["plan"]["code"] == "starter"
    assert body["status"] == "trialing"
    assert body["branches_used"] == 1
    assert body["users_used"] == 1

    branches = client.get("/api/v1/org/branches", headers={"Authorization": f"Bearer {token}"})
    assert branches.status_code == 200
    assert len(branches.json()) == 1
    assert branches.json()[0]["name"] == "Main Store"


def test_signup_rejects_duplicate_email(client):
    payload = _signup_payload()
    first = client.post("/api/v1/auth/signup", json=payload)
    assert first.status_code == 201

    second = _signup_payload(admin_email=payload["admin_email"])
    resp = client.post("/api/v1/auth/signup", json=second)
    assert resp.status_code == 409


def test_signup_rejects_email_already_used_in_a_different_org(client):
    """Distinct from test_signup_rejects_duplicate_email: this specifically
    checks the cross-org path in AuthService.signup (a brand new org has
    no users of its own yet, so the collision can only be caught by a
    global email lookup, not a per-org one)."""
    org_a_payload = _signup_payload()
    assert client.post("/api/v1/auth/signup", json=org_a_payload).status_code == 201

    org_b_payload = _signup_payload(admin_email=org_a_payload["admin_email"])
    resp = client.post("/api/v1/auth/signup", json=org_b_payload)
    assert resp.status_code == 409


def test_list_plans_is_public_and_includes_all_three_tiers(client):
    resp = client.get("/api/v1/subscriptions/plans")
    assert resp.status_code == 200
    codes = {p["code"] for p in resp.json()}
    assert codes == {"starter", "growth", "enterprise"}


def test_starter_plan_branch_limit_enforced(client):
    payload = _signup_payload()
    resp = client.post("/api/v1/auth/signup", json=payload)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    second_branch = client.post(
        "/api/v1/org/branches",
        headers=headers,
        json={"code": "SECOND", "name": "Second Store", "business_type": "grocery", "state_code": "27"},
    )
    assert second_branch.status_code == 422
    assert "at most 1 branches" in second_branch.json()["detail"]


def test_starter_plan_user_limit_enforced(client):
    payload = _signup_payload()
    resp = client.post("/api/v1/auth/signup", json=payload)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Starter allows 3 users; the admin created at signup is #1.
    for i in range(2):
        created = client.post(
            "/api/v1/auth/users",
            headers=headers,
            json={"full_name": f"Cashier {i}", "email": f"cashier{i}-{uuid.uuid4().hex[:6]}@example.com",
                  "password": "CashierPass123!"},
        )
        assert created.status_code == 201, created.text

    over_limit = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"full_name": "One Too Many", "email": f"toomany-{uuid.uuid4().hex[:6]}@example.com",
              "password": "CashierPass123!"},
    )
    assert over_limit.status_code == 422
    assert "at most 3 users" in over_limit.json()["detail"]


def test_checkout_with_mock_adapter_activates_subscription_immediately(client):
    payload = _signup_payload()
    resp = client.post("/api/v1/auth/signup", json=payload)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    checkout = client.post("/api/v1/subscriptions/checkout", headers=headers, json={"plan_code": "growth"})
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["checkout_url"]

    me = client.get("/api/v1/subscriptions/me", headers=headers)
    assert me.json()["plan"]["code"] == "growth"
    assert me.json()["status"] == "active"


def test_lapsed_subscription_locks_out_org_but_not_billing_routes(client, db_session):
    payload = _signup_payload()
    resp = client.post("/api/v1/auth/signup", json=payload)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Simplest reliable lookup: there's only one subscription per fresh org.
    subscription = db_session.query(Subscription).order_by(Subscription.created_at.desc()).first()
    subscription.status = "past_due"
    db_session.commit()

    locked = client.get("/api/v1/org/branches", headers=headers)
    assert locked.status_code == 402

    still_open = client.get("/api/v1/subscriptions/me", headers=headers)
    assert still_open.status_code == 200

    still_login = client.get("/api/v1/auth/me", headers=headers)
    assert still_login.status_code == 200


def test_expired_trial_locks_out_lazily(client, db_session):
    payload = _signup_payload()
    resp = client.post("/api/v1/auth/signup", json=payload)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    subscription = db_session.query(Subscription).order_by(Subscription.created_at.desc()).first()
    subscription.trial_ends_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    locked = client.get("/api/v1/org/branches", headers=headers)
    assert locked.status_code == 402

    db_session.refresh(subscription)
    assert subscription.status == "past_due"


def test_cancel_subscription_locks_out_org(client):
    payload = _signup_payload()
    resp = client.post("/api/v1/auth/signup", json=payload)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    cancel = client.post("/api/v1/subscriptions/cancel", headers=headers)
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "canceled"

    locked = client.get("/api/v1/org/branches", headers=headers)
    assert locked.status_code == 402

    cancel_again = client.post("/api/v1/subscriptions/cancel", headers=headers)
    assert cancel_again.status_code == 409


def test_subscription_webhook_transitions_status(client, db_session):
    payload = _signup_payload()
    resp = client.post("/api/v1/auth/signup", json=payload)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    client.post("/api/v1/subscriptions/checkout", headers=headers, json={"plan_code": "starter"})
    subscription = db_session.query(Subscription).order_by(Subscription.created_at.desc()).first()
    gateway_id = subscription.razorpay_subscription_id
    assert gateway_id

    webhook = client.post(
        "/api/v1/subscriptions/webhook",
        json={"event": "subscription.halted", "payload": {"subscription": {"entity": {"id": gateway_id}}}},
    )
    assert webhook.status_code == 200

    me = client.get("/api/v1/subscriptions/me", headers=headers)
    assert me.json()["status"] == "past_due"


def _signup_and_get_email(client, **overrides):
    payload = _signup_payload(**overrides)
    resp = client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 201, resp.text
    return payload["admin_email"], payload["admin_password"]


def test_forgot_and_reset_password_flow(client, db_session):
    email, old_password = _signup_and_get_email(client)
    forgot = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 202

    user_id = db_session.query(User).filter_by(email=email).one().id
    reset_token = db_session.query(PasswordResetToken).filter_by(user_id=user_id).one()

    reset = client.post(
        "/api/v1/auth/reset-password", json={"token": reset_token.token, "new_password": "BrandNewPass123!"}
    )
    assert reset.status_code == 200

    old_login = client.post("/api/v1/auth/login", data={"username": email, "password": old_password})
    assert old_login.status_code == 401

    new_login = client.post("/api/v1/auth/login", data={"username": email, "password": "BrandNewPass123!"})
    assert new_login.status_code == 200


def test_reset_password_rejects_reused_token(client, db_session):
    email, _ = _signup_and_get_email(client)
    client.post("/api/v1/auth/forgot-password", json={"email": email})
    user_id = db_session.query(User).filter_by(email=email).one().id
    reset_token = db_session.query(PasswordResetToken).filter_by(user_id=user_id).one()

    first = client.post(
        "/api/v1/auth/reset-password", json={"token": reset_token.token, "new_password": "FirstNewPass123!"}
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/auth/reset-password", json={"token": reset_token.token, "new_password": "SecondNewPass123!"}
    )
    assert second.status_code == 422


def test_reset_password_rejects_expired_token(client, db_session):
    email, _ = _signup_and_get_email(client)
    client.post("/api/v1/auth/forgot-password", json={"email": email})
    user_id = db_session.query(User).filter_by(email=email).one().id
    reset_token = db_session.query(PasswordResetToken).filter_by(user_id=user_id).one()
    reset_token.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/reset-password", json={"token": reset_token.token, "new_password": "WontWork123!"}
    )
    assert resp.status_code == 422


def test_forgot_password_does_not_leak_unknown_email(client):
    resp = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 202
