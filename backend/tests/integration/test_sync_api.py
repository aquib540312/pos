import uuid
from datetime import datetime, timezone


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


def _register_terminal(client, seeded_org, name="Till 1", fingerprint=None):
    resp = client.post(
        "/api/v1/sync/register",
        headers=seeded_org["auth_headers"],
        json={"branch_id": str(seeded_org["branch"].id), "name": name, "device_fingerprint": fingerprint or str(uuid.uuid4())},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _offline_sale_payload(seeded_org, quantity=1, client_operation_id=None):
    # Product sale_price=40 @ 18% GST (9% CGST + 9% SGST), rounded to the
    # nearest rupee by the server -- matches test_sales_flow.py's
    # established grand_total for this exact product/quantity/tax combo.
    amount = round(40 * quantity * 1.18)
    return {
        "client_operation_id": client_operation_id or str(uuid.uuid4()),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "branch_id": str(seeded_org["branch"].id),
        "warehouse_id": str(seeded_org["warehouse"].id),
        "items": [{"product_id": str(seeded_org["product"].id), "quantity": quantity}],
        "payments": [{"method": "cash", "amount": amount}],
    }


def test_register_terminal_is_idempotent_by_fingerprint(client, seeded_org):
    fingerprint = "device-abc-123"
    first = _register_terminal(client, seeded_org, name="Till 1", fingerprint=fingerprint)
    second = _register_terminal(client, seeded_org, name="Till 1 renamed", fingerprint=fingerprint)
    assert first["id"] == second["id"]
    assert first["api_key"] == second["api_key"]


def test_push_offline_sale_applies_and_deducts_stock(client, seeded_org, db_session):
    _receive_stock(client, seeded_org, quantity=10)
    terminal = _register_terminal(client, seeded_org)

    resp = client.post(
        "/api/v1/sync/push",
        headers={"X-Terminal-Api-Key": terminal["api_key"]},
        json={"offline_sales": [_offline_sale_payload(seeded_org, quantity=1)]},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["results"][0]
    assert result["status"] == "applied"
    assert result["invoice_id"] is not None

    from app.models.inventory import StockItem

    stock = db_session.query(StockItem).filter_by(product_id=seeded_org["product"].id).one()
    assert float(stock.quantity_on_hand) == 9.0


def test_push_is_idempotent_on_retry(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=10)
    terminal = _register_terminal(client, seeded_org)
    op_id = str(uuid.uuid4())
    payload = {"offline_sales": [_offline_sale_payload(seeded_org, quantity=1, client_operation_id=op_id)]}

    first = client.post("/api/v1/sync/push", headers={"X-Terminal-Api-Key": terminal["api_key"]}, json=payload)
    second = client.post("/api/v1/sync/push", headers={"X-Terminal-Api-Key": terminal["api_key"]}, json=payload)

    assert first.status_code == 200 and second.status_code == 200
    first_result = first.json()["results"][0]
    second_result = second.json()["results"][0]
    assert first_result["status"] == "applied"
    assert second_result["status"] == "applied"
    assert first_result["invoice_id"] == second_result["invoice_id"]


def test_push_with_insufficient_stock_becomes_a_conflict_not_an_oversell(client, seeded_org, db_session):
    """The oversell policy is 'never allow negative stock' -- if another
    terminal already sold the last item before this one synced, the
    offline sale must be parked as a conflict, not silently applied and
    not silently dropped."""
    _receive_stock(client, seeded_org, quantity=1)
    terminal = _register_terminal(client, seeded_org)

    resp = client.post(
        "/api/v1/sync/push",
        headers={"X-Terminal-Api-Key": terminal["api_key"]},
        json={"offline_sales": [_offline_sale_payload(seeded_org, quantity=5)]},
    )
    assert resp.status_code == 200, resp.text
    result = resp.json()["results"][0]
    assert result["status"] == "conflict"
    assert result["conflict_id"] is not None

    from app.models.inventory import StockItem

    stock = db_session.query(StockItem).filter_by(product_id=seeded_org["product"].id).one()
    assert float(stock.quantity_on_hand) == 1.0  # untouched -- never went negative

    conflicts_resp = client.get("/api/v1/sync/conflicts", headers=seeded_org["auth_headers"])
    assert conflicts_resp.status_code == 200
    conflicts = conflicts_resp.json()
    assert len(conflicts) == 1
    assert conflicts[0]["conflict_type"] == "insufficient_stock"
    assert conflicts[0]["status"] == "open"


def test_resolve_conflict_cancel(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=1)
    terminal = _register_terminal(client, seeded_org)
    client.post(
        "/api/v1/sync/push",
        headers={"X-Terminal-Api-Key": terminal["api_key"]},
        json={"offline_sales": [_offline_sale_payload(seeded_org, quantity=5)]},
    )
    conflict = client.get("/api/v1/sync/conflicts", headers=seeded_org["auth_headers"]).json()[0]

    resp = client.post(
        f"/api/v1/sync/conflicts/{conflict['id']}/resolve",
        headers=seeded_org["auth_headers"],
        json={"resolution": "cancel", "notes": "customer left without the item"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["resolution"] == "cancel"

    # Resolving twice is rejected -- it's already been decided.
    again = client.post(
        f"/api/v1/sync/conflicts/{conflict['id']}/resolve",
        headers=seeded_org["auth_headers"],
        json={"resolution": "cancel"},
    )
    assert again.status_code == 409


def test_resolve_conflict_retry_succeeds_after_restock(client, seeded_org, db_session):
    _receive_stock(client, seeded_org, quantity=1)
    terminal = _register_terminal(client, seeded_org)
    client.post(
        "/api/v1/sync/push",
        headers={"X-Terminal-Api-Key": terminal["api_key"]},
        json={"offline_sales": [_offline_sale_payload(seeded_org, quantity=5)]},
    )
    conflict = client.get("/api/v1/sync/conflicts", headers=seeded_org["auth_headers"]).json()[0]

    _receive_stock(client, seeded_org, quantity=10)  # restock enough to cover the shortfall

    resp = client.post(
        f"/api/v1/sync/conflicts/{conflict['id']}/resolve",
        headers=seeded_org["auth_headers"],
        json={"resolution": "retry"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "resolved"
    assert resp.json()["resolution"] == "retry"

    conflicts_after = client.get("/api/v1/sync/conflicts?status_filter=open", headers=seeded_org["auth_headers"]).json()
    assert conflicts_after == []


def test_resolve_conflict_retry_without_restock_stays_unresolved(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=1)
    terminal = _register_terminal(client, seeded_org)
    client.post(
        "/api/v1/sync/push",
        headers={"X-Terminal-Api-Key": terminal["api_key"]},
        json={"offline_sales": [_offline_sale_payload(seeded_org, quantity=5)]},
    )
    conflict = client.get("/api/v1/sync/conflicts", headers=seeded_org["auth_headers"]).json()[0]

    resp = client.post(
        f"/api/v1/sync/conflicts/{conflict['id']}/resolve",
        headers=seeded_org["auth_headers"],
        json={"resolution": "retry"},
    )
    assert resp.status_code == 422


def test_push_rejects_unknown_terminal_api_key(client, seeded_org):
    resp = client.post(
        "/api/v1/sync/push",
        headers={"X-Terminal-Api-Key": "not-a-real-key"},
        json={"offline_sales": []},
    )
    assert resp.status_code == 401


def test_push_batch_over_limit_is_rejected(client, seeded_org):
    terminal = _register_terminal(client, seeded_org)
    sales = [_offline_sale_payload(seeded_org, quantity=1) for _ in range(300)]
    resp = client.post(
        "/api/v1/sync/push", headers={"X-Terminal-Api-Key": terminal["api_key"]}, json={"offline_sales": sales}
    )
    assert resp.status_code == 422


def test_pull_returns_changes_since_cursor_and_supports_partial_sync(client, seeded_org):
    terminal = _register_terminal(client, seeded_org)

    # seeded_org's setup already created a product; capture the cursor
    # after that so this test only sees changes from what it does next.
    baseline = client.get(
        "/api/v1/sync/pull", headers={"X-Terminal-Api-Key": terminal["api_key"]}, params={"cursor": 0}
    ).json()
    cursor = baseline["next_cursor"]

    client.post(
        "/api/v1/party/customers", headers=seeded_org["auth_headers"], json={"name": "Jane Doe", "phone": "9998887777"}
    )
    client.post(
        "/api/v1/catalog/products",
        headers=seeded_org["auth_headers"],
        json={
            "sku": "NEW-001", "name": "New Product", "uom_id": str(seeded_org["uom"].id),
            "hsn_code_id": str(seeded_org["hsn"].id), "mrp": 10, "sale_price": 9, "purchase_price": 7,
        },
    )

    everything = client.get(
        "/api/v1/sync/pull", headers={"X-Terminal-Api-Key": terminal["api_key"]}, params={"cursor": cursor}
    ).json()
    entity_types = {c["entity_type"] for c in everything["changes"]}
    assert entity_types == {"customer", "product"}
    assert everything["has_more"] is False

    only_products = client.get(
        "/api/v1/sync/pull",
        headers={"X-Terminal-Api-Key": terminal["api_key"]},
        params={"cursor": cursor, "entity_types": "product"},
    ).json()
    assert {c["entity_type"] for c in only_products["changes"]} == {"product"}


def test_pull_cursor_pagination_advances_with_has_more(client, seeded_org, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.get_settings(), "sync_pull_page_size", 1)
    terminal = _register_terminal(client, seeded_org)

    client.post(
        "/api/v1/party/customers", headers=seeded_org["auth_headers"], json={"name": "A", "phone": "1111111111"}
    )
    client.post(
        "/api/v1/party/customers", headers=seeded_org["auth_headers"], json={"name": "B", "phone": "2222222222"}
    )

    page1 = client.get(
        "/api/v1/sync/pull", headers={"X-Terminal-Api-Key": terminal["api_key"]}, params={"cursor": 0}
    ).json()
    assert len(page1["changes"]) == 1
    assert page1["has_more"] is True

    page2 = client.get(
        "/api/v1/sync/pull",
        headers={"X-Terminal-Api-Key": terminal["api_key"]},
        params={"cursor": page1["next_cursor"]},
    ).json()
    assert len(page2["changes"]) >= 1
    assert page2["changes"][0]["id"] > page1["changes"][0]["id"]


def test_sync_status_dashboard_reports_terminals_and_open_conflicts(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=1)
    terminal = _register_terminal(client, seeded_org, name="Front Till")
    client.post(
        "/api/v1/sync/push",
        headers={"X-Terminal-Api-Key": terminal["api_key"]},
        json={"offline_sales": [_offline_sale_payload(seeded_org, quantity=5)]},
    )

    resp = client.get("/api/v1/sync/status", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["open_conflicts"] == 1
    assert any(t["name"] == "Front Till" and t["last_seen_at"] is not None for t in body["terminals"])
