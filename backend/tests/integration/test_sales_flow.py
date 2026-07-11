def _receive_stock(client, seeded_org, quantity=100, unit_cost=30):
    supplier_resp = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": "ACME Foods"}
    )
    assert supplier_resp.status_code == 201
    supplier_id = supplier_resp.json()["id"]

    grn_resp = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "items": [
                {"product_id": str(seeded_org["product"].id), "quantity": quantity, "unit_cost": unit_cost}
            ],
        },
    )
    assert grn_resp.status_code == 201, grn_resp.text
    return grn_resp.json()


def test_full_sale_computes_gst_and_deducts_stock(client, seeded_org, db_session):
    _receive_stock(client, seeded_org, quantity=100)

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 3, "discount_amount": 5}],
            "payments": [{"method": "cash", "amount": 136}],
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text
    invoice = sale_resp.json()

    assert invoice["taxable_total"] == 115.0
    assert invoice["cgst_total"] == 10.35
    assert invoice["sgst_total"] == 10.35
    assert invoice["igst_total"] == 0.0
    assert invoice["grand_total"] == 136.0
    assert invoice["status"] == "posted"

    from app.models.inventory import StockItem

    stock = db_session.query(StockItem).filter_by(product_id=seeded_org["product"].id).one()
    assert float(stock.quantity_on_hand) == 97.0


def test_sale_without_enough_stock_is_rejected(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=2)

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 5}],
            "payments": [{"method": "cash", "amount": 236}],
        },
    )
    assert sale_resp.status_code == 409


def test_sale_with_discount_exceeding_line_value_is_rejected_not_500(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=10)

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1, "discount_amount": 1000}],
            "payments": [{"method": "cash", "amount": 1}],
        },
    )
    assert sale_resp.status_code == 422


def test_sale_with_insufficient_payment_is_rejected(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=10)

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [{"method": "cash", "amount": 1}],
        },
    )
    assert sale_resp.status_code == 422


def test_credit_sale_beyond_limit_is_rejected(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=100)

    customer_resp = client.post(
        "/api/v1/party/customers",
        headers=seeded_org["auth_headers"],
        json={"name": "Regular Joe", "is_credit_customer": True, "credit_limit": 50},
    )
    assert customer_resp.status_code == 201
    customer_id = customer_resp.json()["id"]

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "customer_id": customer_id,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 5}],
            "payments": [],
            "is_credit_sale": True,
        },
    )
    assert sale_resp.status_code == 422


def test_credit_sale_within_limit_succeeds_and_updates_balance(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=100)

    customer_resp = client.post(
        "/api/v1/party/customers",
        headers=seeded_org["auth_headers"],
        json={"name": "Good Customer", "is_credit_customer": True, "credit_limit": 1000},
    )
    customer_id = customer_resp.json()["id"]

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "customer_id": customer_id,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 2}],
            "payments": [],
            "is_credit_sale": True,
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text

    customer_check = client.get(f"/api/v1/party/customers/{customer_id}", headers=seeded_org["auth_headers"])
    assert customer_check.json()["credit_balance"] == sale_resp.json()["grand_total"]


def test_return_reverses_stock_and_computes_refund(client, seeded_org, db_session):
    _receive_stock(client, seeded_org, quantity=100)

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 4}],
            "payments": [{"method": "cash", "amount": 189}],
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text
    invoice = sale_resp.json()
    invoice_item_id = invoice["items"][0]["id"]

    return_resp = client.post(
        f"/api/v1/sales/returns?warehouse_id={seeded_org['warehouse'].id}",
        headers=seeded_org["auth_headers"],
        json={
            "original_invoice_id": invoice["id"],
            "reason": "customer changed mind",
            "items": [{"original_invoice_item_id": invoice_item_id, "quantity": 2}],
        },
    )
    assert return_resp.status_code == 201, return_resp.text
    assert return_resp.json()["refund_total"] == invoice["items"][0]["line_total"] / 2

    from app.models.inventory import StockItem

    stock = db_session.query(StockItem).filter_by(product_id=seeded_org["product"].id).one()
    # 100 received - 4 sold + 2 returned = 98
    assert float(stock.quantity_on_hand) == 98.0
