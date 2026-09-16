def _create_table(client, branch_id, headers, number="T1"):
    resp = client.post(
        "/api/v1/dining/tables",
        params={"branch_id": str(branch_id)},
        headers=headers,
        json={"table_number": number, "name": "Window 1", "capacity": 4},
    )
    assert resp.status_code == 201
    return resp.json()


def _receive_stock(client, seeded_org):
    supplier = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": "ACME Foods"}
    )
    grn = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier.json()["id"],
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 100, "unit_cost": 30}],
        },
    )
    assert grn.status_code == 201, grn.text


def test_dining_table_crud(client, seeded_org):
    auth = seeded_org["auth_headers"]
    branch_id = seeded_org["branch"].id
    table = _create_table(client, branch_id, auth)
    assert table["table_number"] == "T1"
    assert table["status"] == "available"
    assert table["active_order_id"] is None

    listed = client.get("/api/v1/dining/tables", params={"branch_id": str(branch_id)}, headers=auth)
    assert listed.status_code == 200
    assert any(t["id"] == table["id"] for t in listed.json())

    # duplicate table number is rejected
    dup = client.post(
        "/api/v1/dining/tables",
        params={"branch_id": str(branch_id)},
        headers=auth,
        json={"table_number": "T1", "capacity": 2},
    )
    assert dup.status_code == 409

    # deactivating a table with no open order works
    deact = client.post(f"/api/v1/dining/tables/{table['id']}/deactivate", headers=auth)
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False


def test_dining_full_flow_till_settle(client, seeded_org):
    auth = seeded_org["auth_headers"]
    branch_id = seeded_org["branch"].id
    warehouse_id = seeded_org["warehouse"].id
    product_id = seeded_org["product"].id

    _receive_stock(client, seeded_org)

    table = _create_table(client, branch_id, auth)

    # open an order on the table
    opened = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(branch_id)},
        headers=auth,
        json={"table_id": table["id"], "note": "Birthday table"},
    )
    assert opened.status_code == 201
    order = opened.json()
    assert order["status"] == "open"
    assert order["table_number"] == "T1"

    # table now shows as occupied with an active order
    listed = client.get("/api/v1/dining/tables", params={"branch_id": str(branch_id)}, headers=auth)
    row = next(t for t in listed.json() if t["id"] == table["id"])
    assert row["status"] == "occupied"
    assert row["active_order_id"] == order["id"]

    # a second open order on the same table is rejected
    dup = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(branch_id)},
        headers=auth,
        json={"table_id": table["id"]},
    )
    assert dup.status_code == 409

    # add items to the order
    added = client.post(
        f"/api/v1/dining/orders/{order['id']}/items",
        headers=auth,
        json={"items": [{"product_id": str(product_id), "quantity": 2}]},
    )
    assert added.status_code == 200
    items = added.json()["items"]
    assert len(items) == 1
    assert items[0]["quantity"] == 2
    assert items[0]["status"] == "pending"
    assert items[0]["product_name"] == "White Bread 400g"
    item_id = items[0]["id"]

    # send to kitchen -> KOT assigned
    kot = client.post(f"/api/v1/dining/orders/{order['id']}/kitchen", headers=auth)
    assert kot.status_code == 200
    kot_item = next(i for i in kot.json()["items"] if i["id"] == item_id)
    assert kot_item["status"] == "preparing"
    assert kot_item["kot_number"] == "KOT-1"

    # estimate now matches the shelf of a later sale: 2 x 40 + 18% GST = 94.4
    est = client.post(f"/api/v1/dining/orders/{order['id']}/estimate", headers=auth)
    assert est.status_code == 200
    assert est.json()["subtotal"] == 80.0
    assert est.json()["taxable_total"] == 80.0
    assert est.json()["grand_total"] == 94.0  # 94.4 rounds to the rupee

    # mark served
    served = client.post(
        f"/api/v1/dining/orders/{order['id']}/serve", headers=auth, json={"item_ids": [item_id]}
    )
    assert served.status_code == 200
    assert next(i for i in served.json()["items"] if i["id"] == item_id)["status"] == "served"

    # settle the bill -> real invoice via SalesService
    settled = client.post(
        f"/api/v1/dining/orders/{order['id']}/settle",
        headers=auth,
        json={
            "warehouse_id": str(warehouse_id),
            "payments": [{"method": "cash", "amount": 94.0}],
        },
    )
    assert settled.status_code == 201, settled.text
    invoice = settled.json()
    assert invoice["grand_total"] == 94.0
    assert invoice["cgst_total"] == 7.2
    assert invoice["sgst_total"] == 7.2

    # order is now paid and table freed up
    order_after = client.get(f"/api/v1/dining/orders/{order['id']}", headers=auth)
    assert order_after.json()["status"] == "paid"
    assert order_after.json()["sales_invoice_id"] == invoice["id"]
    listed = client.get("/api/v1/dining/tables", params={"branch_id": str(branch_id)}, headers=auth)
    row = next(t for t in listed.json() if t["id"] == table["id"])
    assert row["status"] == "available"
    assert row["active_order_id"] is None


def test_dining_insufficient_payment_rejected(client, seeded_org):
    auth = seeded_org["auth_headers"]
    branch_id = seeded_org["branch"].id
    warehouse_id = seeded_org["warehouse"].id
    product_id = seeded_org["product"].id

    _receive_stock(client, seeded_org)

    table = _create_table(client, branch_id, auth)
    opened = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(branch_id)},
        headers=auth,
        json={"table_id": table["id"]},
    ).json()
    client.post(
        f"/api/v1/dining/orders/{opened['id']}/items",
        headers=auth,
        json={"items": [{"product_id": str(product_id), "quantity": 1}]},
    )
    client.post(f"/api/v1/dining/orders/{opened['id']}/kitchen", headers=auth)

    short = client.post(
        f"/api/v1/dining/orders/{opened['id']}/settle",
        headers=auth,
        json={"warehouse_id": str(warehouse_id), "payments": [{"method": "cash", "amount": 10.0}]},
    )
    assert short.status_code == 422

    # order (and table) are untouched by the failed settle
    order_after = client.get(f"/api/v1/dining/orders/{opened['id']}", headers=auth)
    assert order_after.json()["status"] == "open"
    listed = client.get("/api/v1/dining/tables", params={"branch_id": str(branch_id)}, headers=auth)
    row = next(t for t in listed.json() if t["id"] == table["id"])
    assert row["status"] == "occupied"


def test_dining_cancel_order_frees_table(client, seeded_org):
    auth = seeded_org["auth_headers"]
    branch_id = seeded_org["branch"].id
    table = _create_table(client, branch_id, auth)
    opened = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(branch_id)},
        headers=auth,
        json={"table_id": table["id"]},
    ).json()

    cancelled = client.post(f"/api/v1/dining/orders/{opened['id']}/cancel", headers=auth)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    listed = client.get("/api/v1/dining/tables", params={"branch_id": str(branch_id)}, headers=auth)
    row = next(t for t in listed.json() if t["id"] == table["id"])
    assert row["status"] == "available"
    assert row["active_order_id"] is None


def test_dining_ready_and_cancel_item_after_kot(client, seeded_org):
    """Ready status for the kitchen, then void a KOT'd line with an audit note."""
    auth = seeded_org["auth_headers"]
    branch_id = seeded_org["branch"].id
    product_id = seeded_org["product"].id

    table = _create_table(client, branch_id, auth)
    opened = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(branch_id)},
        headers=auth,
        json={"table_id": table["id"]},
    ).json()
    added = client.post(
        f"/api/v1/dining/orders/{opened['id']}/items",
        headers=auth,
        json={"items": [{"product_id": str(product_id), "quantity": 2}]},
    ).json()
    item_id = added["items"][0]["id"]
    client.post(f"/api/v1/dining/orders/{opened['id']}/kitchen", headers=auth)

    # kitchen marks it ready
    ready = client.post(
        f"/api/v1/dining/orders/{opened['id']}/ready",
        headers=auth,
        json={"item_ids": [item_id]},
    )
    assert ready.status_code == 200
    assert next(i for i in ready.json()["items"] if i["id"] == item_id)["status"] == "ready"

    # pending items cannot be marked served
    added2 = client.post(
        f"/api/v1/dining/orders/{opened['id']}/items",
        headers=auth,
        json={"items": [{"product_id": str(product_id), "quantity": 1}]},
    ).json()
    pending_id = added2["items"][-1]["id"]
    bad = client.post(
        f"/api/v1/dining/orders/{opened['id']}/serve",
        headers=auth,
        json={"item_ids": [str(pending_id)]},
    )
    assert bad.status_code == 409

    # void the KOT'd line
    cancelled = client.post(
        f"/api/v1/dining/orders/{opened['id']}/items/{item_id}/cancel",
        headers=auth,
        json={"note": "Guest sent it back"},
    )
    assert cancelled.status_code == 200
    cancelled_item = next(i for i in cancelled.json()["items"] if i["id"] == item_id)
    assert cancelled_item["status"] == "cancelled"
    assert "Guest sent it back" in cancelled_item["note"]


def test_dining_transfer_merge_split(client, seeded_org):
    auth = seeded_org["auth_headers"]
    branch_id = seeded_org["branch"].id
    product_id = seeded_org["product"].id

    t1 = _create_table(client, branch_id, auth, "T1")
    t2 = _create_table(client, branch_id, auth, "T2")
    t3 = _create_table(client, branch_id, auth, "T3")

    # transfer t1 -> t2
    o1 = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(branch_id)},
        headers=auth,
        json={"table_id": t1["id"]},
    ).json()
    moved = client.post(
        f"/api/v1/dining/orders/{o1['id']}/transfer",
        headers=auth,
        json={"target_table_id": t2["id"]},
    )
    assert moved.status_code == 200
    assert moved.json()["table_number"] == "T2"
    listed = client.get("/api/v1/dining/tables", params={"branch_id": str(branch_id)}, headers=auth).json()
    assert next(t for t in listed if t["id"] == t1["id"])["status"] == "available"
    assert next(t for t in listed if t["id"] == t2["id"])["status"] == "occupied"

    # split: open a second order on t3, then merge it into o1
    o2 = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(branch_id)},
        headers=auth,
        json={"table_id": t3["id"]},
    ).json()
    client.post(
        f"/api/v1/dining/orders/{o1['id']}/items",
        headers=auth,
        json={"items": [{"product_id": str(product_id), "quantity": 2}]},
    )
    client.post(
        f"/api/v1/dining/orders/{o2['id']}/items",
        headers=auth,
        json={"items": [{"product_id": str(product_id), "quantity": 1}]},
    )
    merged = client.post(
        f"/api/v1/dining/orders/{o2['id']}/merge",
        headers=auth,
        json={"target_order_id": o1["id"]},
    )
    assert merged.status_code == 200
    items = merged.json()["items"]
    assert sum(float(i["quantity"]) for i in items) == 3
    listed = client.get("/api/v1/dining/tables", params={"branch_id": str(branch_id)}, headers=auth).json()
    assert next(t for t in listed if t["id"] == t1["id"])["status"] == "available"
    assert next(t for t in listed if t["id"] == t2["id"])["status"] == "available"
    assert next(t for t in listed if t["id"] == t3["id"])["status"] == "occupied"
    source_after = client.get(f"/api/v1/dining/orders/{o1['id']}", headers=auth)
    assert source_after.json()["status"] == "cancelled"
    assert "MERGED" in source_after.json()["note"]

    # split: move the pending items onto a fresh order on t2 (freed by merge)
    o3 = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(branch_id)},
        headers=auth,
        json={"table_id": t1["id"]},
    ).json()
    client.post(
        f"/api/v1/dining/orders/{o3['id']}/items",
        headers=auth,
        json={"items": [{"product_id": str(product_id), "quantity": 1}]},
    )
    split_item_id = client.get(f"/api/v1/dining/orders/{o3['id']}", headers=auth).json()["items"][0]["id"]
    split = client.post(
        f"/api/v1/dining/orders/{o3['id']}/split",
        headers=auth,
        json={"target_table_id": t2["id"], "item_ids": [split_item_id]},
    )
    assert split.status_code == 200
    new_order = split.json()
    assert len(new_order["items"]) == 1
    assert new_order["table_number"] == "T2"
    assert len(client.get(f"/api/v1/dining/orders/{o3['id']}", headers=auth).json()["items"]) == 0


def test_dining_idempotent_settle(client, seeded_org):
    """A retried settle returns the same invoice instead of double-billing."""
    auth = seeded_org["auth_headers"]
    branch_id = seeded_org["branch"].id
    warehouse_id = seeded_org["warehouse"].id
    product_id = seeded_org["product"].id

    _receive_stock(client, seeded_org)

    table = _create_table(client, branch_id, auth)
    opened = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(branch_id)},
        headers=auth,
        json={"table_id": table["id"]},
    ).json()
    client.post(
        f"/api/v1/dining/orders/{opened['id']}/items",
        headers=auth,
        json={"items": [{"product_id": str(product_id), "quantity": 1}]},
    )
    client.post(f"/api/v1/dining/orders/{opened['id']}/kitchen", headers=auth)

    body = {"warehouse_id": str(warehouse_id), "payments": [{"method": "cash", "amount": 47.0}]}
    first = client.post(f"/api/v1/dining/orders/{opened['id']}/settle", headers=auth, json=body)
    assert first.status_code == 201, first.text
    second = client.post(f"/api/v1/dining/orders/{opened['id']}/settle", headers=auth, json=body)
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["grand_total"] == first.json()["grand_total"]


def test_dining_parcel_order_no_table_needed(client, seeded_org):
    """Parcel/takeaway orders are table-less, settle with cash, and don't
    occupy or free any dining table."""
    auth = seeded_org["auth_headers"]
    branch_id = seeded_org["branch"].id
    warehouse_id = seeded_org["warehouse"].id
    product_id = seeded_org["product"].id

    _receive_stock(client, seeded_org)
    table = _create_table(client, branch_id, auth)

    opened = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(branch_id)},
        headers=auth,
        json={"order_type": "parcel", "note": "Counter takeaway"},
    )
    assert opened.status_code == 201, opened.text
    order = opened.json()
    assert order["order_type"] == "parcel"
    assert order["table_id"] is None
    assert order["table_number"] == "PARCEL"
    assert order["status"] == "open"

    # the (existing) table stays available -- a parcel never occupies it
    listed = client.get("/api/v1/dining/tables", params={"branch_id": str(branch_id)}, headers=auth)
    row = next(t for t in listed.json() if t["id"] == table["id"])
    assert row["status"] == "available"

    # multiple concurrent parcel orders are allowed (no table to clash)
    second = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str(branch_id)},
        headers=auth,
        json={"order_type": "parcel"},
    )
    assert second.status_code == 201, second.text

    # adding items and sending KOT work exactly like dine-in
    added = client.post(
        f"/api/v1/dining/orders/{order['id']}/items",
        headers=auth,
        json={"items": [{"product_id": str(product_id), "quantity": 2}]},
    )
    assert added.status_code == 200
    item_id = added.json()["items"][0]["id"]
    kot = client.post(f"/api/v1/dining/orders/{order['id']}/kitchen", headers=auth)
    assert kot.status_code == 200
    assert next(i for i in kot.json()["items"] if i["id"] == item_id)["kot_number"] == "KOT-1"

    est = client.post(f"/api/v1/dining/orders/{order['id']}/estimate", headers=auth)
    assert est.json()["grand_total"] == 94.0  # 2 x 40 + 18% GST, rounded

    settled = client.post(
        f"/api/v1/dining/orders/{order['id']}/settle",
        headers=auth,
        json={
            "warehouse_id": str(warehouse_id),
            "payments": [{"method": "cash", "amount": 94.0}],
        },
    )
    assert settled.status_code == 201, settled.text
    assert settled.json()["grand_total"] == 94.0

    order_after = client.get(f"/api/v1/dining/orders/{order['id']}", headers=auth)
    assert order_after.json()["status"] == "paid"


def test_dining_parcel_requires_branch(client, seeded_org):
    """Parcel orders still belong to a branch (GST sourcing needs it)."""
    auth = seeded_org["auth_headers"]
    resp = client.post(
        "/api/v1/dining/orders",
        params={"branch_id": str("00000000-0000-0000-0000-000000000000")},
        headers=auth,
        json={"order_type": "parcel"},
    )
    assert resp.status_code == 404
