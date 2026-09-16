"""Integration tests for the universal-POS product attributes: brands,
weighted items, GST-inclusive pricing, search aliases, variants, opening
stock, and the product image upload/lookup endpoints."""

import uuid

from app.modules.catalog.labels import generate_ean13


def _create_payload(seeded_org, **overrides):
    payload = {
        "sku": f"UP-{uuid.uuid4().hex[:6]}",
        "name": "Universal POS Item",
        "uom_id": str(seeded_org["uom"].id),
        "mrp": 100,
        "sale_price": 90,
    }
    payload.update(overrides)
    return payload


def test_create_weighted_product_with_brand_and_aliases(client, seeded_org):
    body = _create_payload(
        seeded_org, is_weighted=True, brand="Local Farm",
        aliases=["aloo", "aalu", "potato"], reorder_level=20,
    )
    resp = client.post("/api/v1/catalog/products", json=body, headers=seeded_org["auth_headers"])
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["is_weighted"] is True
    assert data["brand"] == "Local Farm"
    assert data["aliases"] == ["aloo", "aalu", "potato"]
    assert data["reorder_level"] == 20.0


def test_alias_search_finds_product(client, seeded_org):
    body = _create_payload(seeded_org, aliases=["desi ghee", "ghee"])
    resp = client.post("/api/v1/catalog/products", json=body, headers=seeded_org["auth_headers"])
    assert resp.status_code == 201
    listed = client.get("/api/v1/catalog/products?search=desi%20ghee", headers=seeded_org["auth_headers"])
    assert listed.status_code == 200
    assert all(p["aliases"] and "desi ghee" in p["aliases"] for p in listed.json())


def test_duplicate_alias_rejected(client, seeded_org):
    first = _create_payload(seeded_org, aliases=["common"])
    assert client.post("/api/v1/catalog/products", json=first, headers=seeded_org["auth_headers"]).status_code == 201
    second = _create_payload(seeded_org, aliases=["common"])
    resp = client.post("/api/v1/catalog/products", json=second, headers=seeded_org["auth_headers"])
    assert resp.status_code == 422
    assert "already used by another product" in resp.json()["detail"]


def test_generate_barcode_produces_valid_ean13(client, seeded_org):
    body = _create_payload(seeded_org, generate_barcode=True, barcode=None)
    resp = client.post("/api/v1/catalog/products", json=body, headers=seeded_org["auth_headers"])
    assert resp.status_code == 201, resp.text
    barcode = resp.json()["barcode"]
    assert barcode is not None
    # EAN-13: 12 digits + check digit, and explicitly round-tripping the
    # check-digit algorithm should confirm it.
    assert len(barcode) == 13 and barcode.isdigit()
    assert generate_ean13(barcode[:12]) == barcode


def test_gst_inclusive_price_derives_exclusive_sale_price(client, seeded_org):
    body = _create_payload(seeded_org, hsn_code_id=str(seeded_org["hsn"].id), mrp=115, sale_price=115,
                           prices_gst_inclusive=True)
    resp = client.post("/api/v1/catalog/products", json=body, headers=seeded_org["auth_headers"])
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["prices_gst_inclusive"] is True
    # 115 inclusive at 15% -> 100 exclusive
    assert round(data["sale_price"], 2) == 100.0
    assert data["tax_rate_percent"] == 15.0


def test_non_inclusive_price_is_stored_as_is(client, seeded_org):
    body = _create_payload(seeded_org, hsn_code_id=str(seeded_org["hsn"].id), mrp=118, sale_price=100,
                           prices_gst_inclusive=False)
    resp = client.post("/api/v1/catalog/products", json=body, headers=seeded_org["auth_headers"])
    data = resp.json()
    assert round(data["sale_price"], 2) == 100.0


def test_create_variant_of_parent(client, seeded_org):
    parent = _create_payload(seeded_org, sku=f"PARENT-{uuid.uuid4().hex[:4]}")
    parent_resp = client.post("/api/v1/catalog/products", json=parent, headers=seeded_org["auth_headers"])
    assert parent_resp.status_code == 201
    parent_id = parent_resp.json()["id"]

    variant = _create_payload(
        seeded_org, parent_product_id=parent_id, variant_label="Red",
    )
    resp = client.post("/api/v1/catalog/products", json=variant, headers=seeded_org["auth_headers"])
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["parent_product_id"] == parent_id
    assert data["variant_label"] == "Red"


def test_variant_requires_label(client, seeded_org):
    parent = _create_payload(seeded_org)
    parent_resp = client.post("/api/v1/catalog/products", json=parent, headers=seeded_org["auth_headers"])
    parent_id = parent_resp.json()["id"]
    variant = _create_payload(seeded_org, parent_product_id=parent_id, variant_label=None)
    resp = client.post("/api/v1/catalog/products", json=variant, headers=seeded_org["auth_headers"])
    assert resp.status_code == 422
    assert "variant_label" in resp.json()["detail"]


def test_opening_stock_on_create(client, seeded_org):
    body = _create_payload(
        seeded_org, initial_stock_qty=25, warehouse_id=str(seeded_org["warehouse"].id),
    )
    resp = client.post("/api/v1/catalog/products", json=body, headers=seeded_org["auth_headers"])
    assert resp.status_code == 201, resp.text

    stock = client.get(
        f"/api/v1/inventory/stock?warehouse_id={seeded_org['warehouse'].id}",
        headers=seeded_org["auth_headers"],
    )
    assert stock.status_code == 200
    rows = stock.json()
    product_id = resp.json()["id"]
    match = [r for r in rows if r["product_id"] == product_id]
    assert match and float(match[0]["quantity_on_hand"]) == 25.0


def test_opening_stock_requires_warehouse(client, seeded_org):
    body = _create_payload(seeded_org, initial_stock_qty=25, warehouse_id=None)
    resp = client.post("/api/v1/catalog/products", json=body, headers=seeded_org["auth_headers"])
    assert resp.status_code == 422
    assert "warehouse" in resp.json()["detail"]


def test_loyalty_exempt_products_skip_point_accrual(client, seeded_org, db_session):
    from app.models.party import Customer

    customer = Customer(
        organization_id=seeded_org["organization"].id, name="Loyal Customer", phone="9999999999",
        is_credit_customer=False, credit_limit=0, credit_balance=0, loyalty_points_balance=0,
    )
    db_session.add(customer)
    db_session.flush()

    exempt = _create_payload(seeded_org, hsn_code_id=str(seeded_org["hsn"].id), sale_price=50, loyalty_exempt=True,
                             initial_stock_qty=10, warehouse_id=str(seeded_org["warehouse"].id))
    exempt_resp = client.post("/api/v1/catalog/products", json=exempt, headers=seeded_org["auth_headers"])
    non_exempt = _create_payload(seeded_org, hsn_code_id=str(seeded_org["hsn"].id), sale_price=50, loyalty_exempt=False,
                                 initial_stock_qty=10, warehouse_id=str(seeded_org["warehouse"].id))
    non_exempt_resp = client.post("/api/v1/catalog/products", json=non_exempt, headers=seeded_org["auth_headers"])

    sale = {
        "branch_id": str(seeded_org["branch"].id),
        "warehouse_id": str(seeded_org["warehouse"].id),
        "customer_id": str(customer.id),
        "is_credit_sale": False,
        "items": [
            {"product_id": exempt_resp.json()["id"], "quantity": 1, "discount_amount": 0},
            {"product_id": non_exempt_resp.json()["id"], "quantity": 1, "discount_amount": 0},
        ],
        "payments": [{"method": "cash", "amount": 115}],
    }
    sale_resp = client.post("/api/v1/sales", json=sale, headers=seeded_org["auth_headers"])
    assert sale_resp.status_code == 201, sale_resp.text

    db_session.refresh(customer)
    # Only the non-exempt line's taxable value (50) accrues points at 1/100
    # per rupee -- the exempt product's 50 contributes nothing.
    assert float(customer.loyalty_points_balance) == round(50 * 0.01, 2)
    assert float(customer.loyalty_points_balance) < round(100 * 0.01, 2)


def test_update_product_sets_brand_and_wholesale_price(client, seeded_org):
    body = _create_payload(seeded_org)
    created = client.post("/api/v1/catalog/products", json=body, headers=seeded_org["auth_headers"]).json()
    resp = client.patch(
        f"/api/v1/catalog/products/{created['id']}",
        json={"brand": "Samsung", "wholesale_price": 1200},
        headers=seeded_org["auth_headers"],
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["brand"] == "Samsung"
    assert data["wholesale_price"] == 1200.0


def test_remove_variant_via_update(client, seeded_org):
    parent = _create_payload(seeded_org)
    parent_id = client.post("/api/v1/catalog/products", json=parent, headers=seeded_org["auth_headers"]).json()["id"]
    variant = _create_payload(seeded_org, parent_product_id=parent_id, variant_label="L")
    variant_id = client.post("/api/v1/catalog/products", json=variant, headers=seeded_org["auth_headers"]).json()["id"]

    resp = client.patch(
        f"/api/v1/catalog/products/{variant_id}", json={"remove_variant": True},
        headers=seeded_org["auth_headers"],
    )
    data = resp.json()
    assert data["parent_product_id"] is None
    assert data["variant_label"] is None


def test_category_name_round_trips(client, seeded_org):
    cat = client.post("/api/v1/catalog/categories", json={"name": "Electronics"}, headers=seeded_org["auth_headers"])
    assert cat.status_code == 201, cat.text
    cat_id = cat.json()["id"]
    body = _create_payload(seeded_org, category_id=str(cat_id))
    created = client.post("/api/v1/catalog/products", json=body, headers=seeded_org["auth_headers"]).json()
    assert created["category_name"] == "Electronics"


def test_image_upload_and_lookup(client, seeded_org):
    body = _create_payload(seeded_org)
    created = client.post("/api/v1/catalog/products", json=body, headers=seeded_org["auth_headers"]).json()
    pid = created["id"]

    png = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 16)
    upload = client.post(
        f"/api/v1/catalog/products/{pid}/image",
        files={"file": ("tiny.png", png, "image/png")},
        headers=seeded_org["auth_headers"],
    )
    assert upload.status_code == 200, upload.text
    assert upload.json()["image_path"] == f"{pid}.png"

    lookup = client.get(f"/api/v1/catalog/products/{pid}/image.png", headers=seeded_org["auth_headers"])
    assert lookup.status_code == 200
    assert lookup.headers["content-type"] == "image/png"


def test_image_upload_rejects_bad_type(client, seeded_org):
    body = _create_payload(seeded_org)
    created = client.post("/api/v1/catalog/products", json=body, headers=seeded_org["auth_headers"]).json()
    resp = client.post(
        f"/api/v1/catalog/products/{created['id']}/image",
        files={"file": ("x.txt", b"hello", "text/plain")},
        headers=seeded_org["auth_headers"],
    )
    assert resp.status_code == 422
