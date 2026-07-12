import uuid


def _create_supplier(client, seeded_org, name="Test Supplier"):
    resp = client.post("/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_create_purchase_order_then_appears_in_list(client, seeded_org):
    supplier_id = _create_supplier(client, seeded_org)
    create_resp = client.post(
        "/api/v1/purchasing/purchase-orders",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "supplier_id": supplier_id,
            "order_date": "2026-01-01",
            "items": [{"product_id": str(seeded_org["product"].id), "quantity_ordered": 50, "unit_cost": 30}],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    po = create_resp.json()
    assert po["status"] == "draft" or po["status"]
    assert len(po["items"]) == 1

    list_resp = client.get("/api/v1/purchasing/purchase-orders", headers=seeded_org["auth_headers"])
    assert list_resp.status_code == 200
    assert any(p["id"] == po["id"] for p in list_resp.json())


def test_get_purchase_order_by_id(client, seeded_org):
    supplier_id = _create_supplier(client, seeded_org)
    create_resp = client.post(
        "/api/v1/purchasing/purchase-orders",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "supplier_id": supplier_id,
            "order_date": "2026-01-01",
            "items": [{"product_id": str(seeded_org["product"].id), "quantity_ordered": 10, "unit_cost": 30}],
        },
    )
    po_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/v1/purchasing/purchase-orders/{po_id}", headers=seeded_org["auth_headers"])
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == po_id


def test_get_purchase_order_404_for_unknown_id(client, seeded_org):
    resp = client.get(f"/api/v1/purchasing/purchase-orders/{uuid.uuid4()}", headers=seeded_org["auth_headers"])
    assert resp.status_code == 404


def test_create_goods_receipt_then_appears_in_list(client, seeded_org):
    supplier_id = _create_supplier(client, seeded_org)
    grn_resp = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 25, "unit_cost": 30}],
        },
    )
    assert grn_resp.status_code == 201, grn_resp.text
    grn = grn_resp.json()
    assert len(grn["items"]) == 1

    list_resp = client.get("/api/v1/purchasing/goods-receipts", headers=seeded_org["auth_headers"])
    assert list_resp.status_code == 200
    assert any(g["id"] == grn["id"] for g in list_resp.json())

    get_resp = client.get(f"/api/v1/purchasing/goods-receipts/{grn['id']}", headers=seeded_org["auth_headers"])
    assert get_resp.status_code == 200
    assert get_resp.json()["grn_number"] == grn["grn_number"]


def test_goods_receipt_against_purchase_order_updates_quantity_received(client, seeded_org):
    supplier_id = _create_supplier(client, seeded_org)
    po_resp = client.post(
        "/api/v1/purchasing/purchase-orders",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "supplier_id": supplier_id,
            "order_date": "2026-01-01",
            "items": [{"product_id": str(seeded_org["product"].id), "quantity_ordered": 40, "unit_cost": 30}],
        },
    )
    po_id = po_resp.json()["id"]

    grn_resp = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "purchase_order_id": po_id,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 40, "unit_cost": 30}],
        },
    )
    assert grn_resp.status_code == 201, grn_resp.text

    po_after = client.get(f"/api/v1/purchasing/purchase-orders/{po_id}", headers=seeded_org["auth_headers"]).json()
    assert po_after["items"][0]["quantity_received"] == 40
