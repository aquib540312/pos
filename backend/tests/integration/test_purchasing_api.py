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


def _supplier_payable(client, seeded_org, supplier_id):
    suppliers = client.get("/api/v1/party/suppliers", headers=seeded_org["auth_headers"]).json()
    return next(s["payable_balance"] for s in suppliers if s["id"] == supplier_id)


def _stock_on_hand(client, seeded_org, product_id):
    stock = client.get(
        "/api/v1/inventory/stock",
        headers=seeded_org["auth_headers"],
        params={"warehouse_id": str(seeded_org["warehouse"].id)},
    ).json()
    return sum(s["quantity_on_hand"] for s in stock if s["product_id"] == product_id)


def test_goods_receipt_with_free_bonus_pieces_adds_full_quantity_to_stock(client, seeded_org):
    """A supplier "10+1 free" scheme: 100 paid + 10 free = 110 physical
    units received, all sellable, but only the 100 paid units are owed."""
    supplier_id = _create_supplier(client, seeded_org)
    stock_before = _stock_on_hand(client, seeded_org, str(seeded_org["product"].id))

    grn_resp = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "items": [
                {"product_id": str(seeded_org["product"].id), "quantity": 110, "free_quantity": 10, "unit_cost": 30}
            ],
        },
    )
    assert grn_resp.status_code == 201, grn_resp.text
    item = grn_resp.json()["items"][0]
    assert item["quantity"] == 110
    assert item["free_quantity"] == 10

    stock_after = _stock_on_hand(client, seeded_org, str(seeded_org["product"].id))
    assert stock_after - stock_before == 110


def test_goods_receipt_with_free_pieces_only_bills_paid_quantity(client, seeded_org):
    supplier_id = _create_supplier(client, seeded_org)
    payable_before = _supplier_payable(client, seeded_org, supplier_id)

    client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "items": [
                {"product_id": str(seeded_org["product"].id), "quantity": 110, "free_quantity": 10, "unit_cost": 30}
            ],
        },
    )

    payable_after = _supplier_payable(client, seeded_org, supplier_id)
    # Only the 100 paid units at 30 each = 3000 are owed -- the 10 free units
    # cost nothing -- plus 18% GST (540) the supplier bills on the paid amount.
    assert payable_after - payable_before == 3540


def test_goods_receipt_rejects_free_quantity_exceeding_total(client, seeded_org):
    supplier_id = _create_supplier(client, seeded_org)
    resp = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "items": [
                {"product_id": str(seeded_org["product"].id), "quantity": 10, "free_quantity": 11, "unit_cost": 30}
            ],
        },
    )
    assert resp.status_code == 422


def test_goods_receipt_against_po_counts_only_paid_quantity_toward_received(client, seeded_org):
    """Bonus stock isn't part of what was ordered -- a PO's
    quantity_received should advance only by the paid quantity."""
    supplier_id = _create_supplier(client, seeded_org)
    po_resp = client.post(
        "/api/v1/purchasing/purchase-orders",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "supplier_id": supplier_id,
            "order_date": "2026-01-01",
            "items": [{"product_id": str(seeded_org["product"].id), "quantity_ordered": 100, "unit_cost": 30}],
        },
    )
    po_id = po_resp.json()["id"]

    client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "purchase_order_id": po_id,
            "items": [
                {"product_id": str(seeded_org["product"].id), "quantity": 110, "free_quantity": 10, "unit_cost": 30}
            ],
        },
    )

    po_after = client.get(f"/api/v1/purchasing/purchase-orders/{po_id}", headers=seeded_org["auth_headers"]).json()
    assert po_after["items"][0]["quantity_received"] == 100
