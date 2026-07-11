def test_login_success_and_me(client, seeded_org):
    resp = client.post(
        "/api/v1/auth/login", data={"username": "admin@test.local", "password": "TestPass123!"}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "admin@test.local"


def test_login_wrong_password_rejected(client, seeded_org):
    resp = client.post(
        "/api/v1/auth/login", data={"username": "admin@test.local", "password": "wrong"}
    )
    assert resp.status_code == 401


def test_protected_endpoint_requires_token(client, seeded_org):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_user_with_no_roles_is_denied_permission_gated_action(client, seeded_org, db_session):
    from app.core.security import create_access_token
    from app.modules.auth.service import AuthService

    no_role_user = AuthService(db_session).create_user(
        organization_id=seeded_org["organization"].id,
        full_name="No Roles",
        email="noroles@test.local",
        password="TestPass123!",
    )
    db_session.commit()
    token = create_access_token(subject=str(no_role_user.id))

    resp = client.post(
        "/api/v1/catalog/products",
        headers={"Authorization": f"Bearer {token}"},
        json={"sku": "DUP-001", "name": "Dup", "uom_id": str(seeded_org["uom"].id), "mrp": 10, "sale_price": 10},
    )
    assert resp.status_code == 403


def test_admin_can_create_product(client, seeded_org):
    resp = client.post(
        "/api/v1/catalog/products",
        headers=seeded_org["auth_headers"],
        json={"sku": "DUP-001", "name": "Dup", "uom_id": str(seeded_org["uom"].id), "mrp": 10, "sale_price": 10},
    )
    assert resp.status_code == 201
