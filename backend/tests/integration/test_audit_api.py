def test_audit_log_records_user_creation(client, seeded_org):
    create_resp = client.post(
        "/api/v1/auth/users",
        headers=seeded_org["auth_headers"],
        json={"full_name": "Audit Test User", "email": "audittest@example.com", "password": "AuditPass123!"},
    )
    assert create_resp.status_code == 201, create_resp.text
    new_user_id = create_resp.json()["id"]

    logs_resp = client.get("/api/v1/audit/logs", headers=seeded_org["auth_headers"])
    assert logs_resp.status_code == 200
    logs = logs_resp.json()
    matching = [log for log in logs if log["action"] == "user.create" and log["entity_id"] == new_user_id]
    assert len(matching) == 1
    assert matching[0]["user_id"] == str(seeded_org["admin"].id)


def test_audit_logs_require_org_manage_permission(client, seeded_org, db_session):
    from app.core.security import create_access_token
    from app.modules.auth.service import AuthService

    no_role_user = AuthService(db_session).create_user(
        organization_id=seeded_org["organization"].id,
        full_name="No Roles",
        email="noroles-audit@example.com",
        password="TestPass123!",
    )
    db_session.commit()
    token = create_access_token(subject=str(no_role_user.id))

    resp = client.get("/api/v1/audit/logs", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
