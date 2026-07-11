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


def _complete_sale(client, seeded_org):
    _receive_stock(client, seeded_org)
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
    return sale_resp.json()


def test_escpos_preview_returns_real_receipt_bytes(client, seeded_org):
    invoice = _complete_sale(client, seeded_org)
    resp = client.get(f"/api/v1/printing/receipt/{invoice['id']}/escpos", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/octet-stream"
    body = resp.content.decode("latin1")
    assert "White Bread 400g" in body  # real product name, not a raw UUID
    assert invoice["invoice_number"] in body


def test_escpos_preview_404_for_unknown_invoice(client, seeded_org):
    import uuid

    resp = client.get(f"/api/v1/printing/receipt/{uuid.uuid4()}/escpos", headers=seeded_org["auth_headers"])
    assert resp.status_code == 404


def test_print_receipt_queues_job_without_hardware(client, seeded_org, monkeypatch):
    invoice = _complete_sale(client, seeded_org)
    captured = []
    monkeypatch.setattr(
        "app.modules.printing.api.print_receipt_task.delay", lambda payload: captured.append(payload)
    )

    resp = client.post(f"/api/v1/printing/receipt/{invoice['id']}/print", headers=seeded_org["auth_headers"])
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued"
    assert len(captured) == 1
    assert captured[0]["invoice_number"] == invoice["invoice_number"]


def test_print_receipt_broker_failure_does_not_error(client, seeded_org, monkeypatch):
    invoice = _complete_sale(client, seeded_org)

    def _broker_down(*args, **kwargs):
        raise ConnectionError("broker unreachable")

    monkeypatch.setattr("app.modules.printing.api.print_receipt_task.delay", _broker_down)

    resp = client.post(f"/api/v1/printing/receipt/{invoice['id']}/print", headers=seeded_org["auth_headers"])
    assert resp.status_code == 202
    assert resp.json()["status"] == "queue_failed"


def test_print_service_disabled_by_default_does_not_attempt_network(seeded_org):
    from app.modules.printing.service import PrintService

    service = PrintService()
    assert service.settings.printer_enabled is False
    result = service.print_invoice({"invoice_number": "INV/TEST"})
    assert result is False
