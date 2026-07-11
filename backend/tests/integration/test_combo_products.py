def _create_component_product(client, seeded_org, sku, name, sale_price=10):
    resp = client.post(
        "/api/v1/catalog/products",
        headers=seeded_org["auth_headers"],
        json={
            "sku": sku,
            "name": name,
            "uom_id": str(seeded_org["uom"].id),
            "hsn_code_id": str(seeded_org["hsn"].id),
            "mrp": sale_price,
            "sale_price": sale_price,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _receive_stock(client, seeded_org, product_id, quantity, unit_cost=5):
    supplier_resp = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": f"Supplier for {product_id}"}
    )
    supplier_id = supplier_resp.json()["id"]
    grn_resp = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "items": [{"product_id": product_id, "quantity": quantity, "unit_cost": unit_cost}],
        },
    )
    assert grn_resp.status_code == 201, grn_resp.text


def _stock_on_hand(client, seeded_org, product_id):
    resp = client.get(
        "/api/v1/inventory/stock",
        headers=seeded_org["auth_headers"],
        params={"warehouse_id": str(seeded_org["warehouse"].id)},
    )
    return sum(s["quantity_on_hand"] for s in resp.json() if s["product_id"] == product_id)


def test_combo_requires_at_least_one_component(client, seeded_org):
    resp = client.post(
        "/api/v1/catalog/products",
        headers=seeded_org["auth_headers"],
        json={
            "sku": "COMBO-EMPTY",
            "name": "Empty combo",
            "uom_id": str(seeded_org["uom"].id),
            "hsn_code_id": str(seeded_org["hsn"].id),
            "mrp": 100,
            "sale_price": 100,
            "is_combo": True,
            "combo_components": [],
        },
    )
    assert resp.status_code == 422


def test_non_combo_product_rejects_components(client, seeded_org):
    water = _create_component_product(client, seeded_org, "WTR-001", "Water Bottle")
    resp = client.post(
        "/api/v1/catalog/products",
        headers=seeded_org["auth_headers"],
        json={
            "sku": "NOTCOMBO",
            "name": "Not a combo",
            "uom_id": str(seeded_org["uom"].id),
            "hsn_code_id": str(seeded_org["hsn"].id),
            "mrp": 10,
            "sale_price": 10,
            "is_combo": False,
            "combo_components": [{"component_product_id": water["id"], "quantity": 1}],
        },
    )
    assert resp.status_code == 422


def test_combo_cannot_nest_another_combo(client, seeded_org):
    water = _create_component_product(client, seeded_org, "WTR-002", "Water Bottle 2")
    combo_resp = client.post(
        "/api/v1/catalog/products",
        headers=seeded_org["auth_headers"],
        json={
            "sku": "COMBO-A",
            "name": "Combo A",
            "uom_id": str(seeded_org["uom"].id),
            "hsn_code_id": str(seeded_org["hsn"].id),
            "mrp": 50,
            "sale_price": 50,
            "is_combo": True,
            "combo_components": [{"component_product_id": water["id"], "quantity": 1}],
        },
    )
    assert combo_resp.status_code == 201, combo_resp.text
    combo_a = combo_resp.json()

    nested_resp = client.post(
        "/api/v1/catalog/products",
        headers=seeded_org["auth_headers"],
        json={
            "sku": "COMBO-B",
            "name": "Combo B",
            "uom_id": str(seeded_org["uom"].id),
            "hsn_code_id": str(seeded_org["hsn"].id),
            "mrp": 60,
            "sale_price": 60,
            "is_combo": True,
            "combo_components": [{"component_product_id": combo_a["id"], "quantity": 1}],
        },
    )
    assert nested_resp.status_code == 422


def test_create_combo_product_returns_component_details(client, seeded_org):
    chips = _create_component_product(client, seeded_org, "CHP-001", "Chips Packet", sale_price=20)
    soda = _create_component_product(client, seeded_org, "SOD-001", "Soda Can", sale_price=15)

    resp = client.post(
        "/api/v1/catalog/products",
        headers=seeded_org["auth_headers"],
        json={
            "sku": "COMBO-SNACK",
            "name": "Snack Combo",
            "uom_id": str(seeded_org["uom"].id),
            "hsn_code_id": str(seeded_org["hsn"].id),
            "mrp": 30,
            "sale_price": 30,
            "is_combo": True,
            "combo_components": [
                {"component_product_id": chips["id"], "quantity": 1},
                {"component_product_id": soda["id"], "quantity": 2},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    combo = resp.json()
    assert combo["is_combo"] is True
    components_by_name = {c["component_product_name"]: c["quantity"] for c in combo["combo_components"]}
    assert components_by_name == {"Chips Packet": 1.0, "Soda Can": 2.0}


def test_selling_combo_decrements_component_stock_not_combo_itself(client, seeded_org):
    chips = _create_component_product(client, seeded_org, "CHP-002", "Chips Packet 2", sale_price=20)
    soda = _create_component_product(client, seeded_org, "SOD-002", "Soda Can 2", sale_price=15)
    _receive_stock(client, seeded_org, chips["id"], quantity=50)
    _receive_stock(client, seeded_org, soda["id"], quantity=50)

    combo_resp = client.post(
        "/api/v1/catalog/products",
        headers=seeded_org["auth_headers"],
        json={
            "sku": "COMBO-SNACK-2",
            "name": "Snack Combo 2",
            "uom_id": str(seeded_org["uom"].id),
            "hsn_code_id": str(seeded_org["hsn"].id),
            "mrp": 30,
            "sale_price": 30,
            "is_combo": True,
            "combo_components": [
                {"component_product_id": chips["id"], "quantity": 1},
                {"component_product_id": soda["id"], "quantity": 2},
            ],
        },
    )
    combo = combo_resp.json()

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": combo["id"], "quantity": 3}],
            "payments": [{"method": "cash", "amount": 106}],  # 3*30=90 taxable, 18% => 16.2 -> 106.2 -> 106
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text
    invoice = sale_resp.json()
    assert invoice["items"][0]["batch_id"] is None  # no single batch for a combo line

    assert _stock_on_hand(client, seeded_org, chips["id"]) == 50 - 3 * 1
    assert _stock_on_hand(client, seeded_org, soda["id"]) == 50 - 3 * 2
    assert _stock_on_hand(client, seeded_org, combo["id"]) == 0  # combo itself never carries stock


def test_returning_combo_restores_component_stock(client, seeded_org):
    chips = _create_component_product(client, seeded_org, "CHP-003", "Chips Packet 3", sale_price=20)
    soda = _create_component_product(client, seeded_org, "SOD-003", "Soda Can 3", sale_price=15)
    _receive_stock(client, seeded_org, chips["id"], quantity=50)
    _receive_stock(client, seeded_org, soda["id"], quantity=50)

    combo_resp = client.post(
        "/api/v1/catalog/products",
        headers=seeded_org["auth_headers"],
        json={
            "sku": "COMBO-SNACK-3",
            "name": "Snack Combo 3",
            "uom_id": str(seeded_org["uom"].id),
            "hsn_code_id": str(seeded_org["hsn"].id),
            "mrp": 30,
            "sale_price": 30,
            "is_combo": True,
            "combo_components": [
                {"component_product_id": chips["id"], "quantity": 1},
                {"component_product_id": soda["id"], "quantity": 2},
            ],
        },
    )
    combo = combo_resp.json()

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": combo["id"], "quantity": 3}],
            "payments": [{"method": "cash", "amount": 106}],
        },
    )
    invoice = sale_resp.json()
    invoice_item_id = invoice["items"][0]["id"]

    return_resp = client.post(
        f"/api/v1/sales/returns?warehouse_id={seeded_org['warehouse'].id}",
        headers=seeded_org["auth_headers"],
        json={
            "original_invoice_id": invoice["id"],
            "items": [{"original_invoice_item_id": invoice_item_id, "quantity": 1}],
        },
    )
    assert return_resp.status_code == 201, return_resp.text

    # sold 3 combos (chips -3, soda -6), returned 1 combo (chips +1, soda +2)
    assert _stock_on_hand(client, seeded_org, chips["id"]) == 50 - 3 + 1
    assert _stock_on_hand(client, seeded_org, soda["id"]) == 50 - 6 + 2
