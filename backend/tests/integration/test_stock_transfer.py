from app.models.organization import Warehouse


def _second_warehouse(db_session, seeded_org):
    warehouse = Warehouse(branch_id=seeded_org["branch"].id, code="WH2", name="Second Warehouse", is_default=False)
    db_session.add(warehouse)
    db_session.commit()
    return warehouse


def _receive_stock(client, seeded_org, warehouse_id=None, quantity=50):
    supplier_resp = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": "ACME Foods"}
    )
    supplier_id = supplier_resp.json()["id"]
    grn_resp = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(warehouse_id or seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": quantity, "unit_cost": 30}],
        },
    )
    assert grn_resp.status_code == 201, grn_resp.text


def test_full_transfer_lifecycle_moves_stock(client, seeded_org, db_session):
    warehouse2 = _second_warehouse(db_session, seeded_org)
    _receive_stock(client, seeded_org, quantity=50)

    create_resp = client.post(
        "/api/v1/inventory/transfers",
        headers=seeded_org["auth_headers"],
        json={
            "source_warehouse_id": str(seeded_org["warehouse"].id),
            "destination_warehouse_id": str(warehouse2.id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 20}],
        },
    )
    assert create_resp.status_code == 201, create_resp.text
    transfer = create_resp.json()
    assert transfer["status"] == "draft"

    # stock hasn't moved yet in draft status
    stock_resp = client.get(
        "/api/v1/inventory/stock", headers=seeded_org["auth_headers"], params={"warehouse_id": str(seeded_org["warehouse"].id)}
    )
    assert sum(s["quantity_on_hand"] for s in stock_resp.json()) == 50

    dispatch_resp = client.post(
        f"/api/v1/inventory/transfers/{transfer['id']}/dispatch", headers=seeded_org["auth_headers"]
    )
    assert dispatch_resp.status_code == 200, dispatch_resp.text
    assert dispatch_resp.json()["status"] == "dispatched"

    source_stock = client.get(
        "/api/v1/inventory/stock", headers=seeded_org["auth_headers"], params={"warehouse_id": str(seeded_org["warehouse"].id)}
    ).json()
    assert sum(s["quantity_on_hand"] for s in source_stock) == 30  # 50 - 20 dispatched

    dest_stock_before = client.get(
        "/api/v1/inventory/stock", headers=seeded_org["auth_headers"], params={"warehouse_id": str(warehouse2.id)}
    ).json()
    assert dest_stock_before == []  # in transit, not yet arrived

    receive_resp = client.post(
        f"/api/v1/inventory/transfers/{transfer['id']}/receive", headers=seeded_org["auth_headers"]
    )
    assert receive_resp.status_code == 200, receive_resp.text
    assert receive_resp.json()["status"] == "received"

    dest_stock_after = client.get(
        "/api/v1/inventory/stock", headers=seeded_org["auth_headers"], params={"warehouse_id": str(warehouse2.id)}
    ).json()
    assert sum(s["quantity_on_hand"] for s in dest_stock_after) == 20


def test_dispatch_with_insufficient_stock_is_rejected(client, seeded_org, db_session):
    warehouse2 = _second_warehouse(db_session, seeded_org)
    _receive_stock(client, seeded_org, quantity=5)

    create_resp = client.post(
        "/api/v1/inventory/transfers",
        headers=seeded_org["auth_headers"],
        json={
            "source_warehouse_id": str(seeded_org["warehouse"].id),
            "destination_warehouse_id": str(warehouse2.id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 100}],
        },
    )
    transfer_id = create_resp.json()["id"]

    dispatch_resp = client.post(f"/api/v1/inventory/transfers/{transfer_id}/dispatch", headers=seeded_org["auth_headers"])
    assert dispatch_resp.status_code == 409


def test_cannot_dispatch_twice_or_receive_before_dispatch(client, seeded_org, db_session):
    warehouse2 = _second_warehouse(db_session, seeded_org)
    _receive_stock(client, seeded_org, quantity=50)

    create_resp = client.post(
        "/api/v1/inventory/transfers",
        headers=seeded_org["auth_headers"],
        json={
            "source_warehouse_id": str(seeded_org["warehouse"].id),
            "destination_warehouse_id": str(warehouse2.id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 10}],
        },
    )
    transfer_id = create_resp.json()["id"]

    receive_too_early = client.post(f"/api/v1/inventory/transfers/{transfer_id}/receive", headers=seeded_org["auth_headers"])
    assert receive_too_early.status_code == 409

    first_dispatch = client.post(f"/api/v1/inventory/transfers/{transfer_id}/dispatch", headers=seeded_org["auth_headers"])
    assert first_dispatch.status_code == 200

    second_dispatch = client.post(f"/api/v1/inventory/transfers/{transfer_id}/dispatch", headers=seeded_org["auth_headers"])
    assert second_dispatch.status_code == 409


def test_transfer_to_same_warehouse_is_rejected(client, seeded_org):
    resp = client.post(
        "/api/v1/inventory/transfers",
        headers=seeded_org["auth_headers"],
        json={
            "source_warehouse_id": str(seeded_org["warehouse"].id),
            "destination_warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
        },
    )
    assert resp.status_code == 422
