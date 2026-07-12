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


def _sell(client, seeded_org, amount, shift_id, method="cash"):
    payload = {
        "branch_id": str(seeded_org["branch"].id),
        "warehouse_id": str(seeded_org["warehouse"].id),
        "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
        "payments": [{"method": method, "amount": amount}],
        "shift_id": shift_id,
    }
    resp = client.post("/api/v1/sales", headers=seeded_org["auth_headers"], json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_current_shift_is_null_when_none_open(client, seeded_org):
    resp = client.get(
        "/api/v1/billing/shifts/current",
        headers=seeded_org["auth_headers"],
        params={"branch_id": str(seeded_org["branch"].id)},
    )
    assert resp.status_code == 200
    assert resp.json() is None


def test_open_shift_then_current_shift_reflects_it(client, seeded_org):
    open_resp = client.post(
        "/api/v1/billing/shifts/open",
        headers=seeded_org["auth_headers"],
        json={"branch_id": str(seeded_org["branch"].id), "opening_cash": 2000},
    )
    assert open_resp.status_code == 201, open_resp.text
    shift_id = open_resp.json()["id"]

    current_resp = client.get(
        "/api/v1/billing/shifts/current",
        headers=seeded_org["auth_headers"],
        params={"branch_id": str(seeded_org["branch"].id)},
    )
    assert current_resp.status_code == 200
    current = current_resp.json()
    assert current["id"] == shift_id
    assert current["status"] == "open"
    assert current["opening_cash"] == 2000
    assert current["running_cash_sales"] == 0


def test_cannot_open_second_shift_while_one_is_open(client, seeded_org):
    first = client.post(
        "/api/v1/billing/shifts/open",
        headers=seeded_org["auth_headers"],
        json={"branch_id": str(seeded_org["branch"].id), "opening_cash": 1000},
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/billing/shifts/open",
        headers=seeded_org["auth_headers"],
        json={"branch_id": str(seeded_org["branch"].id), "opening_cash": 1000},
    )
    assert second.status_code == 409


def test_current_shift_running_cash_sales_reflects_cash_payments_only(client, seeded_org):
    _receive_stock(client, seeded_org)
    open_resp = client.post(
        "/api/v1/billing/shifts/open",
        headers=seeded_org["auth_headers"],
        json={"branch_id": str(seeded_org["branch"].id), "opening_cash": 1000},
    )
    shift_id = open_resp.json()["id"]

    _sell(client, seeded_org, amount=47, shift_id=shift_id, method="cash")
    _sell(client, seeded_org, amount=47, shift_id=shift_id, method="card")  # not cash -- must not count

    current = client.get(
        "/api/v1/billing/shifts/current",
        headers=seeded_org["auth_headers"],
        params={"branch_id": str(seeded_org["branch"].id)},
    ).json()
    assert current["running_cash_sales"] == 47


def test_close_shift_computes_variance(client, seeded_org):
    _receive_stock(client, seeded_org)
    open_resp = client.post(
        "/api/v1/billing/shifts/open",
        headers=seeded_org["auth_headers"],
        json={"branch_id": str(seeded_org["branch"].id), "opening_cash": 1000},
    )
    shift_id = open_resp.json()["id"]
    _sell(client, seeded_org, amount=47, shift_id=shift_id, method="cash")

    close_resp = client.post(
        f"/api/v1/billing/shifts/{shift_id}/close",
        headers=seeded_org["auth_headers"],
        json={"counted_closing_cash": 1035},
    )
    assert close_resp.status_code == 200, close_resp.text
    closed = close_resp.json()
    assert closed["status"] == "closed"
    assert closed["expected_closing_cash"] == 1047
    assert closed["counted_closing_cash"] == 1035
    assert closed["cash_variance"] == -12

    # Closed shift no longer shows up as "current".
    current_resp = client.get(
        "/api/v1/billing/shifts/current",
        headers=seeded_org["auth_headers"],
        params={"branch_id": str(seeded_org["branch"].id)},
    )
    assert current_resp.json() is None


def test_close_shift_twice_conflicts(client, seeded_org):
    open_resp = client.post(
        "/api/v1/billing/shifts/open",
        headers=seeded_org["auth_headers"],
        json={"branch_id": str(seeded_org["branch"].id), "opening_cash": 1000},
    )
    shift_id = open_resp.json()["id"]
    client.post(
        f"/api/v1/billing/shifts/{shift_id}/close",
        headers=seeded_org["auth_headers"],
        json={"counted_closing_cash": 1000},
    )

    second_close = client.post(
        f"/api/v1/billing/shifts/{shift_id}/close",
        headers=seeded_org["auth_headers"],
        json={"counted_closing_cash": 1000},
    )
    assert second_close.status_code == 409


def test_list_shifts_returns_most_recent_first(client, seeded_org):
    ids = []
    for opening in (1000, 1500, 2000):
        open_resp = client.post(
            "/api/v1/billing/shifts/open",
            headers=seeded_org["auth_headers"],
            json={"branch_id": str(seeded_org["branch"].id), "opening_cash": opening},
        )
        shift_id = open_resp.json()["id"]
        ids.append(shift_id)
        client.post(
            f"/api/v1/billing/shifts/{shift_id}/close",
            headers=seeded_org["auth_headers"],
            json={"counted_closing_cash": opening},
        )

    list_resp = client.get(
        "/api/v1/billing/shifts",
        headers=seeded_org["auth_headers"],
        params={"branch_id": str(seeded_org["branch"].id)},
    )
    assert list_resp.status_code == 200
    listed_ids = [s["id"] for s in list_resp.json()]
    assert listed_ids[:3] == list(reversed(ids))
