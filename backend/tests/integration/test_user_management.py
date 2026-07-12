def _cashier_role_id(client, seeded_org):
    roles = client.get("/api/v1/rbac/roles", headers=seeded_org["auth_headers"]).json()
    return next(r["id"] for r in roles if r["name"] == "cashier")


def test_create_user_appears_in_list_with_roles(client, seeded_org):
    cashier_role_id = _cashier_role_id(client, seeded_org)
    create_resp = client.post(
        "/api/v1/auth/users",
        headers=seeded_org["auth_headers"],
        json={
            "full_name": "New Cashier",
            "email": "cashier1@example.com",
            "password": "CashierPass123!",
            "role_ids": [cashier_role_id],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert created["is_active"] is True
    assert created["role_names"] == ["cashier"]

    list_resp = client.get("/api/v1/auth/users", headers=seeded_org["auth_headers"])
    assert list_resp.status_code == 200
    emails = {u["email"] for u in list_resp.json()}
    assert "cashier1@example.com" in emails


def test_duplicate_email_rejected(client, seeded_org):
    first = client.post(
        "/api/v1/auth/users",
        headers=seeded_org["auth_headers"],
        json={"full_name": "Original", "email": "dup@example.com", "password": "SomePass123!"},
    )
    assert first.status_code == 201, first.text

    dup = client.post(
        "/api/v1/auth/users",
        headers=seeded_org["auth_headers"],
        json={"full_name": "Dup", "email": "dup@example.com", "password": "SomePass123!"},
    )
    assert dup.status_code == 409


def test_deactivate_user_then_login_fails(client, seeded_org):
    cashier_role_id = _cashier_role_id(client, seeded_org)
    create_resp = client.post(
        "/api/v1/auth/users",
        headers=seeded_org["auth_headers"],
        json={
            "full_name": "Temp Cashier",
            "email": "temp@example.com",
            "password": "TempPass123!",
            "role_ids": [cashier_role_id],
        },
    )
    user_id = create_resp.json()["id"]

    deactivate_resp = client.patch(
        f"/api/v1/auth/users/{user_id}/active", headers=seeded_org["auth_headers"], json={"is_active": False}
    )
    assert deactivate_resp.status_code == 200
    assert deactivate_resp.json()["is_active"] is False

    login_resp = client.post("/api/v1/auth/login", data={"username": "temp@example.com", "password": "TempPass123!"})
    assert login_resp.status_code == 401


def test_admin_cannot_deactivate_own_account(client, seeded_org):
    admin_id = str(seeded_org["admin"].id)
    resp = client.patch(
        f"/api/v1/auth/users/{admin_id}/active", headers=seeded_org["auth_headers"], json={"is_active": False}
    )
    assert resp.status_code == 422


def test_update_user_roles_replaces_assignment(client, seeded_org):
    roles = client.get("/api/v1/rbac/roles", headers=seeded_org["auth_headers"]).json()
    cashier_role_id = next(r["id"] for r in roles if r["name"] == "cashier")
    manager_role_id = next(r["id"] for r in roles if r["name"] == "manager")

    create_resp = client.post(
        "/api/v1/auth/users",
        headers=seeded_org["auth_headers"],
        json={
            "full_name": "Role Change",
            "email": "rolechange@example.com",
            "password": "RolePass123!",
            "role_ids": [cashier_role_id],
        },
    )
    user_id = create_resp.json()["id"]

    update_resp = client.patch(
        f"/api/v1/auth/users/{user_id}/roles", headers=seeded_org["auth_headers"], json={"role_ids": [manager_role_id]}
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["role_names"] == ["manager"]
