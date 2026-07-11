def _receive_stock(client, seeded_org, quantity=10):
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


def test_sale_with_customer_phone_queues_receipt_sms(client, seeded_org, monkeypatch):
    _receive_stock(client, seeded_org)
    customer_resp = client.post(
        "/api/v1/party/customers",
        headers=seeded_org["auth_headers"],
        json={"name": "Jane Doe", "phone": "9876543210"},
    )
    customer_id = customer_resp.json()["id"]

    captured = []
    monkeypatch.setattr(
        "app.modules.sales.api.send_notification_task.delay",
        lambda channel, to, message: captured.append((channel, to, message)),
    )

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "customer_id": customer_id,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [{"method": "cash", "amount": 47}],
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text
    assert len(captured) == 1
    channel, to, message = captured[0]
    assert channel == "sms"
    assert to == "9876543210"
    assert sale_resp.json()["invoice_number"] in message


def test_sale_without_customer_does_not_attempt_sms(client, seeded_org, monkeypatch):
    _receive_stock(client, seeded_org)

    def _fail(*args, **kwargs):
        raise AssertionError("should not be called when there is no customer")

    monkeypatch.setattr("app.modules.sales.api.send_notification_task.delay", _fail)

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [{"method": "cash", "amount": 47}],
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text


def test_notification_dispatch_failure_does_not_break_checkout(client, seeded_org, monkeypatch):
    _receive_stock(client, seeded_org)
    customer_resp = client.post(
        "/api/v1/party/customers",
        headers=seeded_org["auth_headers"],
        json={"name": "Jane Doe", "phone": "9876543210"},
    )
    customer_id = customer_resp.json()["id"]

    def _broker_down(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("app.modules.sales.api.send_notification_task.delay", _broker_down)

    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "customer_id": customer_id,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [{"method": "cash", "amount": 47}],
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text  # sale still succeeds despite broker failure
