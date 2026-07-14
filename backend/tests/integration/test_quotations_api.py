import uuid


def _receive_stock(client, seeded_org, quantity=100, unit_cost=30):
    supplier_resp = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": f"Supplier {uuid.uuid4()}"}
    )
    assert supplier_resp.status_code == 201
    supplier_id = supplier_resp.json()["id"]
    grn_resp = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": quantity, "unit_cost": unit_cost}],
        },
    )
    assert grn_resp.status_code == 201, grn_resp.text


def _create_quotation(client, seeded_org, **overrides):
    payload = {
        "branch_id": str(seeded_org["branch"].id),
        "quotation_date": "2026-01-01",
        "items": [{"product_id": str(seeded_org["product"].id), "quantity": 2}],
    }
    payload.update(overrides)
    resp = client.post("/api/v1/sales/quotations", headers=seeded_org["auth_headers"], json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_quotation_computes_grand_total_from_product_sale_price(client, seeded_org):
    quotation = _create_quotation(client, seeded_org)
    assert quotation["status"] == "draft"
    assert quotation["grand_total"] == 80.0  # 2 x sale_price(40), no discount
    assert quotation["items"][0]["unit_price"] == 40.0
    assert quotation["converted_invoice_id"] is None


def test_create_quotation_with_explicit_price_and_discount(client, seeded_org):
    quotation = _create_quotation(
        client,
        seeded_org,
        items=[
            {
                "product_id": str(seeded_org["product"].id),
                "quantity": 3,
                "unit_price": 50,
                "discount_amount": 10,
            }
        ],
    )
    assert quotation["grand_total"] == 140.0  # 3*50 - 10


def test_create_quotation_rejects_unknown_product(client, seeded_org):
    resp = client.post(
        "/api/v1/sales/quotations",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "quotation_date": "2026-01-01",
            "items": [{"product_id": str(uuid.uuid4()), "quantity": 1}],
        },
    )
    assert resp.status_code == 404


def test_create_quotation_rejects_discount_exceeding_line_value(client, seeded_org):
    resp = client.post(
        "/api/v1/sales/quotations",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "quotation_date": "2026-01-01",
            "items": [
                {"product_id": str(seeded_org["product"].id), "quantity": 1, "unit_price": 40, "discount_amount": 50}
            ],
        },
    )
    assert resp.status_code == 422


def test_list_quotations_includes_created(client, seeded_org):
    quotation = _create_quotation(client, seeded_org)
    resp = client.get("/api/v1/sales/quotations", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200
    assert any(q["id"] == quotation["id"] for q in resp.json())


def test_get_quotation_404_for_unknown_id(client, seeded_org):
    resp = client.get(f"/api/v1/sales/quotations/{uuid.uuid4()}", headers=seeded_org["auth_headers"])
    assert resp.status_code == 404


def test_send_quotation_transitions_draft_to_sent(client, seeded_org):
    quotation = _create_quotation(client, seeded_org)
    resp = client.post(f"/api/v1/sales/quotations/{quotation['id']}/send", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "sent"


def test_send_quotation_rejects_when_not_draft(client, seeded_org):
    quotation = _create_quotation(client, seeded_org)
    client.post(f"/api/v1/sales/quotations/{quotation['id']}/send", headers=seeded_org["auth_headers"])

    second = client.post(f"/api/v1/sales/quotations/{quotation['id']}/send", headers=seeded_org["auth_headers"])
    assert second.status_code == 409


def test_expire_quotation(client, seeded_org):
    quotation = _create_quotation(client, seeded_org)
    resp = client.post(f"/api/v1/sales/quotations/{quotation['id']}/expire", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200
    assert resp.json()["status"] == "expired"


def test_convert_quotation_to_sale_creates_invoice_and_deducts_stock(client, seeded_org, db_session):
    _receive_stock(client, seeded_org, quantity=50)
    quotation = _create_quotation(client, seeded_org)

    convert_resp = client.post(
        f"/api/v1/sales/quotations/{quotation['id']}/convert",
        headers=seeded_org["auth_headers"],
        json={"warehouse_id": str(seeded_org["warehouse"].id), "payments": [{"method": "cash", "amount": 94}]},
    )
    assert convert_resp.status_code == 201, convert_resp.text
    invoice = convert_resp.json()
    assert invoice["grand_total"] == 94.0  # 2 x 40 = 80 taxable, +18% GST = 94.4 -> rounds to 94

    quotation_after = client.get(
        f"/api/v1/sales/quotations/{quotation['id']}", headers=seeded_org["auth_headers"]
    ).json()
    assert quotation_after["status"] == "converted"
    assert quotation_after["converted_invoice_id"] == invoice["id"]

    from app.models.inventory import StockItem

    stock = db_session.query(StockItem).filter_by(product_id=seeded_org["product"].id).one()
    assert float(stock.quantity_on_hand) == 48.0  # 50 received - 2 sold


def test_convert_already_converted_quotation_rejected(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=50)
    quotation = _create_quotation(client, seeded_org)
    client.post(
        f"/api/v1/sales/quotations/{quotation['id']}/convert",
        headers=seeded_org["auth_headers"],
        json={"warehouse_id": str(seeded_org["warehouse"].id), "payments": [{"method": "cash", "amount": 94}]},
    )

    second = client.post(
        f"/api/v1/sales/quotations/{quotation['id']}/convert",
        headers=seeded_org["auth_headers"],
        json={"warehouse_id": str(seeded_org["warehouse"].id), "payments": [{"method": "cash", "amount": 94}]},
    )
    assert second.status_code == 409


def test_convert_expired_quotation_rejected(client, seeded_org):
    quotation = _create_quotation(client, seeded_org, valid_until="2020-01-01")

    resp = client.post(
        f"/api/v1/sales/quotations/{quotation['id']}/convert",
        headers=seeded_org["auth_headers"],
        json={"warehouse_id": str(seeded_org["warehouse"].id), "payments": [{"method": "cash", "amount": 94}]},
    )
    assert resp.status_code == 422
