
from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, Perm
from app.core.security import create_access_token
from app.models.organization import Branch, Organization, Warehouse
from app.modules.auth.service import AuthService
from app.modules.rbac.repository import PermissionRepository
from app.modules.rbac.service import RoleService


def _make_org(db, name: str, code: str, warehouse_code: str = "WH"):
    """A second tenant with its own branch + warehouse + admin, same shape
    as the seeded_org fixture so cross-tenant tests can prove isolation."""
    org = Organization(legal_name=name, trade_name=name, default_state_code="27")
    db.add(org)
    db.flush()
    branch = Branch(organization_id=org.id, code=code, name=name, business_type="grocery", state_code="27")
    db.add(branch)
    db.flush()
    warehouse = Warehouse(branch_id=branch.id, code=warehouse_code, name=name, is_default=True)
    db.add(warehouse)
    db.flush()

    PermissionRepository(db).ensure_seeded(Perm.ALL_PERMISSIONS)
    role_service = RoleService(db)
    admin_role = None
    for role_name, perm_codes in DEFAULT_ROLE_PERMISSIONS.items():
        role = role_service.create_role(org.id, role_name, f"{role_name} role", perm_codes)
        if role_name == "admin":
            admin_role = role
    admin = AuthService(db).create_user(
        organization_id=org.id, full_name="Admin", email=f"admin-{code}@test.local", password="TestPass123!",
        role_ids=[admin_role.id],
    )
    db.commit()
    token = create_access_token(subject=str(admin.id), extra_claims={"org": str(org.id)})
    return {
        "organization": org,
        "branch": branch,
        "warehouse": warehouse,
        "admin": admin,
        "auth_headers": {"Authorization": f"Bearer {token}"},
    }


def _receive_stock(client, org, quantity=100, unit_cost=30):
    supplier = client.post("/api/v1/party/suppliers", headers=org["auth_headers"], json={"name": "ACME Foods"})
    grn = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=org["auth_headers"],
        json={
            "warehouse_id": str(org["warehouse"].id),
            "supplier_id": supplier.json()["id"],
            "items": [{"product_id": str(org["product"].id), "quantity": quantity, "unit_cost": unit_cost}],
        },
    )
    assert grn.status_code == 201, grn.text


def _sell(client, org, quantity=2, amount=94):
    resp = client.post(
        "/api/v1/sales",
        headers=org["auth_headers"],
        json={
            "branch_id": str(org["branch"].id),
            "warehouse_id": str(org["warehouse"].id),
            "items": [{"product_id": str(org["product"].id), "quantity": quantity}],
            "payments": [{"method": "cash", "amount": amount}],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_table(client, branch_id, headers, number="T1"):
    resp = client.post(
        "/api/v1/dining/tables",
        params={"branch_id": str(branch_id)},
        headers=headers,
        json={"table_number": number, "name": "Window", "capacity": 4},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_c1_cross_org_branch_and_warehouse_rejected(client, seeded_org, db_session):
    """A tenant must never write a sale into another tenant's branch/warehouse."""
    auth = seeded_org["auth_headers"]
    foreign = _make_org(db_session, "Foreign Retail", "FGN", "WHF")
    body = {
        "branch_id": str(seeded_org["branch"].id),
        "warehouse_id": str(seeded_org["warehouse"].id),
        "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
        "payments": [{"method": "cash", "amount": 50.0}],
    }
    for field, wrong_value in (
        ("branch_id", foreign["branch"].id),
        ("warehouse_id", foreign["warehouse"].id),
    ):
        bad = dict(body)
        bad[field] = str(wrong_value)
        resp = client.post("/api/v1/sales", headers=auth, json=bad)
        assert resp.status_code == 404, (field, resp.text)


def test_c2_cross_org_reads_404(client, seeded_org, db_session):
    """GET sale / quotation / return must 404 across tenants, never leak."""
    auth = seeded_org["auth_headers"]
    foreign = _make_org(db_session, "Foreign Retail", "FGN", "WHF")

    _receive_stock(client, seeded_org)
    invoice = _sell(client, seeded_org)

    invoice_item_id = invoice["items"][0]["id"]
    ret = client.post(
        f"/api/v1/sales/returns?warehouse_id={seeded_org['warehouse'].id}",
        headers=auth,
        json={
            "original_invoice_id": invoice["id"],
            "reason": "guest test",
            "items": [{"original_invoice_item_id": invoice_item_id, "quantity": 1}],
        },
    )
    assert ret.status_code == 201, ret.text
    return_id = ret.json()["id"]

    q = client.post(
        "/api/v1/sales/quotations",
        headers=auth,
        json={
            "branch_id": str(seeded_org["branch"].id),
            "quotation_date": "2026-08-17",
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
        },
    )
    assert q.status_code == 201, q.text
    quotation_id = q.json()["id"]

    foreign_auth = foreign["auth_headers"]
    assert client.get(f"/api/v1/sales/{invoice['id']}", headers=foreign_auth).status_code == 404
    assert client.get(f"/api/v1/sales/quotations/{quotation_id}", headers=foreign_auth).status_code == 404
    assert client.get(f"/api/v1/sales/returns/{return_id}", headers=foreign_auth).status_code == 404


def test_c3_cross_org_branch_rejected_for_tables_and_orders(client, seeded_org, db_session):
    """Dining create_table + open_order validate branch ownership (404)."""
    auth = seeded_org["auth_headers"]
    foreign = _make_org(db_session, "Foreign Retail", "FGN", "WHF")
    foreign_branch_id = foreign["branch"].id

    create_table = client.post(
        "/api/v1/dining/tables",
        params={"branch_id": str(foreign_branch_id)},
        headers=auth,
        json={"table_number": "F1", "name": "Sneaky", "capacity": 2},
    )
    assert create_table.status_code == 404, create_table.text

    own_table = client.post(
        "/api/v1/dining/tables",
        params={"branch_id": str(seeded_org["branch"].id)},
        headers=auth,
        json={"table_number": "T1", "name": "Window", "capacity": 4},
    ).json()

    open_foreign = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(foreign_branch_id)},
        headers=auth,
        json={"table_id": own_table["id"]},
    )
    assert open_foreign.status_code == 404, open_foreign.text


def test_h1_h2_cross_branch_transfer_and_split_rejected(client, seeded_org, db_session):
    """Transfer/split of an order onto another branch's table is rejected,
    and splitting a KOT'd item is a conflict, not a 500."""
    auth = seeded_org["auth_headers"]
    org = seeded_org["organization"]
    product_id = seeded_org["product"].id

    # a second branch of the SAME org (dining rooms are per-branch)
    other_branch = Branch(
        organization_id=org.id, code="BR2", name="Second Floor", business_type="fandb", state_code="27"
    )
    db_session.add(other_branch)
    db_session.flush()
    other_warehouse = Warehouse(branch_id=other_branch.id, code="WH2", name="Second Floor WH", is_default=False)
    db_session.add(other_warehouse)
    db_session.commit()

    t_a = _create_table(client, seeded_org["branch"].id, auth, "T1")
    t_b = _create_table(client, other_branch.id, auth, "TB")

    opened = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(seeded_org["branch"].id)},
        headers=auth,
        json={"table_id": t_a["id"]},
    ).json()

    # H1: transfer to the other branch's table -> 422 validation error
    transfer = client.post(
        f"/api/v1/dining/orders/{opened['id']}/transfer",
        headers=auth,
        json={"target_table_id": t_b["id"]},
    )
    assert transfer.status_code == 422, transfer.text
    assert "different branch" in transfer.json().get("detail", "")

    # H2: split onto the other branch's table -> 422
    client.post(
        f"/api/v1/dining/orders/{opened['id']}/items",
        headers=auth,
        json={"items": [{"product_id": str(product_id), "quantity": 1}]},
    )
    item_id = client.get(f"/api/v1/dining/orders/{opened['id']}", headers=auth).json()["items"][0]["id"]
    split = client.post(
        f"/api/v1/dining/orders/{opened['id']}/split",
        headers=auth,
        json={"target_table_id": t_b["id"], "item_ids": [item_id]},
    )
    assert split.status_code == 422, split.text

    # H2: split a KOT'd (non-pending) item -> 409 conflict, not a 500
    client.post(
        f"/api/v1/dining/orders/{opened['id']}/kitchen",
        headers=auth,
    )
    fresh_table = _create_table(client, seeded_org["branch"].id, auth, "TF")
    fresh = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(seeded_org["branch"].id)},
        headers=auth,
        json={"table_id": fresh_table["id"]},
    ).json()
    client.post(
        f"/api/v1/dining/orders/{fresh['id']}/items",
        headers=auth,
        json={"items": [{"product_id": str(product_id), "quantity": 1}]},
    )
    kot_item = client.post(f"/api/v1/dining/orders/{fresh['id']}/kitchen", headers=auth).json()["items"][0]
    target = _create_table(client, seeded_org["branch"].id, auth, "TK")
    split_kot = client.post(
        f"/api/v1/dining/orders/{fresh['id']}/split",
        headers=auth,
        json={"target_table_id": target["id"], "item_ids": [kot_item["id"]]},
    )
    assert split_kot.status_code == 409, split_kot.text
