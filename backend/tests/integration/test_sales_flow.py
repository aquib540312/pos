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


def _paid_gateway_transaction(db_session, seeded_org, amount, reference="qr_paid_test"):
    from app.models.payments import PaymentGatewayTransaction

    transaction = PaymentGatewayTransaction(
        organization_id=seeded_org["organization"].id,
        provider="razorpay",
        gateway_reference=reference,
        amount=amount,
        status="paid",
        receipt_reference="INV/2026/000050",
    )
    db_session.add(transaction)
    db_session.commit()
    return transaction


def test_sale_with_paid_gateway_transaction_is_completed_and_transaction_reserved(client, seeded_org, db_session):
    _receive_stock(client, seeded_org, quantity=10)
    transaction = _paid_gateway_transaction(db_session, seeded_org, amount=47.0)

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [],
            "payment_gateway_transaction_id": str(transaction.id),
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text
    invoice = sale_resp.json()
    assert invoice["grand_total"] == 47.0
    upi_payments = [p for p in invoice["payments"] if p["method"] == "upi"]
    assert len(upi_payments) == 1
    assert upi_payments[0]["amount"] == 47.0
    assert upi_payments[0]["reference"] == "qr_paid_test"

    db_session.refresh(transaction)
    assert str(transaction.invoice_id) == invoice["id"]


def test_reusing_a_consumed_gateway_transaction_is_rejected(client, seeded_org, db_session):
    """The FK set on the first sale makes the transaction single-use --
    a retried or duplicated POST /sales with the same transaction id must
    not be allowed to pay for a second invoice."""
    _receive_stock(client, seeded_org, quantity=10)
    transaction = _paid_gateway_transaction(db_session, seeded_org, amount=47.0)

    first = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [],
            "payment_gateway_transaction_id": str(transaction.id),
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
            "payments": [],
            "payment_gateway_transaction_id": str(transaction.id),
        },
    )
    assert second.status_code == 409, second.text


def test_sale_with_unpaid_gateway_transaction_is_rejected(client, seeded_org, db_session):
    from app.models.payments import PaymentGatewayTransaction

    _receive_stock(client, seeded_org, quantity=10)
    transaction = PaymentGatewayTransaction(
        organization_id=seeded_org["organization"].id,
        provider="razorpay",
        gateway_reference="qr_not_paid",
        amount=47.0,
        status="created",
        receipt_reference="INV/2026/000051",
    )
    db_session.add(transaction)
    db_session.commit()

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [],
            "payment_gateway_transaction_id": str(transaction.id),
        },
    )
    assert sale_resp.status_code == 422, sale_resp.text


def test_sale_uses_gateway_transaction_amount_not_client_supplied_amount(client, seeded_org, db_session):
    """The client cannot inflate what a QR payment is worth: even if the
    request also carries an (invalid, mismatched) cash tender, the
    server-derived UPI amount always comes from the transaction row."""
    _receive_stock(client, seeded_org, quantity=10)
    transaction = _paid_gateway_transaction(db_session, seeded_org, amount=47.0, reference="qr_amount_test")

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [{"method": "cash", "amount": 0.01}],
            "payment_gateway_transaction_id": str(transaction.id),
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text
    invoice = sale_resp.json()
    upi_payments = [p for p in invoice["payments"] if p["method"] == "upi"]
    assert upi_payments[0]["amount"] == 47.0


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
