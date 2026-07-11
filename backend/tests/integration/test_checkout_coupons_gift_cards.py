def _receive_stock(client, seeded_org, quantity=50):
    supplier_resp = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": "ACME Foods"}
    )
    supplier_id = supplier_resp.json()["id"]
    grn_resp = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": quantity, "unit_cost": 30}],
        },
    )
    assert grn_resp.status_code == 201, grn_resp.text


def test_coupon_discount_reduces_grand_total(client, seeded_org):
    _receive_stock(client, seeded_org)

    coupon_resp = client.post(
        "/api/v1/loyalty/coupons",
        headers=seeded_org["auth_headers"],
        json={
            "code": "SAVE10",
            "discount_type": "flat",
            "discount_value": 10,
            "min_order_value": 0,
            "valid_from": "2020-01-01",
        },
    )
    assert coupon_resp.status_code == 201, coupon_resp.text

    # 1 * 40 = 40 taxable, 18% => 7.2 tax => 47.2, minus 10 flat coupon => 37.2 -> 37
    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [{"method": "cash", "amount": 37}],
            "coupon_code": "SAVE10",
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text
    invoice = sale_resp.json()
    assert invoice["coupon_code"] == "SAVE10"
    assert invoice["coupon_discount_amount"] == 10.0
    assert invoice["grand_total"] == 37.0


def test_coupon_redemption_count_increments(client, seeded_org, db_session):
    _receive_stock(client, seeded_org)
    client.post(
        "/api/v1/loyalty/coupons",
        headers=seeded_org["auth_headers"],
        json={
            "code": "ONESHOT",
            "discount_type": "flat",
            "discount_value": 5,
            "min_order_value": 0,
            "max_redemptions": 1,
            "valid_from": "2020-01-01",
        },
    )

    first = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [{"method": "cash", "amount": 42}],
            "coupon_code": "ONESHOT",
        },
    )
    assert first.status_code == 201, first.text

    second = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [{"method": "cash", "amount": 47}],
            "coupon_code": "ONESHOT",
        },
    )
    assert second.status_code == 422  # redemption limit reached


def test_coupon_below_minimum_order_value_is_rejected(client, seeded_org):
    _receive_stock(client, seeded_org)
    client.post(
        "/api/v1/loyalty/coupons",
        headers=seeded_org["auth_headers"],
        json={
            "code": "BIG100",
            "discount_type": "flat",
            "discount_value": 20,
            "min_order_value": 500,
            "valid_from": "2020-01-01",
        },
    )

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [{"method": "cash", "amount": 47}],
            "coupon_code": "BIG100",
        },
    )
    assert sale_resp.status_code == 422


def test_unknown_coupon_code_is_rejected(client, seeded_org):
    _receive_stock(client, seeded_org)
    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [{"method": "cash", "amount": 47}],
            "coupon_code": "DOES-NOT-EXIST",
        },
    )
    assert sale_resp.status_code == 404


def test_gift_card_redemption_covers_part_of_the_bill(client, seeded_org, db_session):
    _receive_stock(client, seeded_org)

    card_resp = client.post(
        "/api/v1/loyalty/gift-cards",
        headers=seeded_org["auth_headers"],
        json={"card_number": "GC-100", "initial_value": 100},
    )
    assert card_resp.status_code == 201, card_resp.text

    # 1 * 40 = 40 taxable, 18% => 7.2 tax => 47.2 -> 47; redeem 20 from gift card, pay 27 cash
    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [{"method": "cash", "amount": 27}],
            "gift_card_number": "GC-100",
            "gift_card_amount": 20,
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text
    invoice = sale_resp.json()
    assert invoice["grand_total"] == 47.0
    methods = {p["method"]: p["amount"] for p in invoice["payments"]}
    assert methods == {"cash": 27.0, "gift_card": 20.0}

    from app.models.loyalty import GiftCard

    card = db_session.query(GiftCard).filter_by(card_number="GC-100").one()
    assert float(card.balance) == 80.0


def test_gift_card_insufficient_balance_is_rejected(client, seeded_org):
    _receive_stock(client, seeded_org)
    client.post(
        "/api/v1/loyalty/gift-cards",
        headers=seeded_org["auth_headers"],
        json={"card_number": "GC-LOW", "initial_value": 5},
    )

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [{"method": "cash", "amount": 47}],
            "gift_card_number": "GC-LOW",
            "gift_card_amount": 20,
        },
    )
    assert sale_resp.status_code == 422
