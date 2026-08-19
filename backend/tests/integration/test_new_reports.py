import datetime as dt
import uuid

from app.core.timezones import ist_today


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


def _sell(client, seeded_org, quantity, amount, method="cash", shift_id=None):
    payload = {
        "branch_id": str(seeded_org["branch"].id),
        "warehouse_id": str(seeded_org["warehouse"].id),
        "items": [{"product_id": str(seeded_org["product"].id), "quantity": quantity}],
        "payments": [{"method": method, "amount": amount}],
    }
    if shift_id:
        payload["shift_id"] = shift_id
    resp = client.post("/api/v1/sales", headers=seeded_org["auth_headers"], json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _today_range():
    today = ist_today().isoformat()
    return today, today


def test_top_products_ranks_by_revenue(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=100)
    _sell(client, seeded_org, quantity=3, amount=142)  # 3*40=120 taxable, 18% => 21.6 -> 141.6 -> 142

    start, end = _today_range()
    resp = client.get(
        "/api/v1/reports/top-products", headers=seeded_org["auth_headers"], params={"start": start, "end": end}
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["product_id"] == str(seeded_org["product"].id)
    assert rows[0]["quantity_sold"] == 3.0
    # Sum of line_total, not grand_total -- the invoice-level round_off
    # adjustment isn't distributed back onto individual line items.
    assert rows[0]["revenue"] == 141.6


def test_top_products_respects_limit(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=100)
    _sell(client, seeded_org, quantity=1, amount=47)

    start, end = _today_range()
    resp = client.get(
        "/api/v1/reports/top-products",
        headers=seeded_org["auth_headers"],
        params={"start": start, "end": end, "limit": 1},
    )
    assert resp.status_code == 200
    assert len(resp.json()) <= 1


def test_payment_breakdown_groups_by_method(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=100)
    _sell(client, seeded_org, quantity=1, amount=47, method="cash")
    _sell(client, seeded_org, quantity=1, amount=47, method="upi")
    _sell(client, seeded_org, quantity=1, amount=47, method="upi")

    start, end = _today_range()
    resp = client.get(
        "/api/v1/reports/payment-breakdown", headers=seeded_org["auth_headers"], params={"start": start, "end": end}
    )
    assert resp.status_code == 200, resp.text
    by_method = {row["method"]: row for row in resp.json()}
    assert by_method["cash"]["payment_count"] == 1
    assert by_method["cash"]["total_amount"] == 47.0
    assert by_method["upi"]["payment_count"] == 2
    assert by_method["upi"]["total_amount"] == 94.0


def test_sales_by_cashier_attributes_to_shift_user(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=100)

    shift_resp = client.post(
        "/api/v1/billing/shifts/open",
        headers=seeded_org["auth_headers"],
        json={"branch_id": str(seeded_org["branch"].id), "opening_cash": 500},
    )
    assert shift_resp.status_code == 201, shift_resp.text
    shift_id = shift_resp.json()["id"]

    _sell(client, seeded_org, quantity=1, amount=47, shift_id=shift_id)
    _sell(client, seeded_org, quantity=2, amount=94, shift_id=shift_id)

    start, end = _today_range()
    resp = client.get(
        "/api/v1/reports/sales-by-cashier", headers=seeded_org["auth_headers"], params={"start": start, "end": end}
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["user_id"] == str(seeded_org["admin"].id)
    assert rows[0]["invoice_count"] == 2
    assert rows[0]["total_grand_total"] == 141.0


def test_sales_by_cashier_excludes_invoices_without_a_shift(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=100)
    _sell(client, seeded_org, quantity=1, amount=47)  # no shift_id

    start, end = _today_range()
    resp = client.get(
        "/api/v1/reports/sales-by-cashier", headers=seeded_org["auth_headers"], params={"start": start, "end": end}
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_supplier_purchase_returns_lists_buy_and_return_side_by_side(client, seeded_org):
    headers = seeded_org["auth_headers"]

    def _create_supplier(name):
        resp = client.post("/api/v1/party/suppliers", headers=headers, json={"name": name})
        assert resp.status_code == 201
        return resp.json()["id"]

    def _grn(supplier_id, quantity, unit_cost):
        resp = client.post(
            "/api/v1/purchasing/goods-receipts",
            headers=headers,
            json={
                "warehouse_id": str(seeded_org["warehouse"].id),
                "supplier_id": supplier_id,
                "items": [{"product_id": str(seeded_org["product"].id), "quantity": quantity, "unit_cost": unit_cost}],
            },
        )
        assert resp.status_code == 201, resp.text
        return resp.json()

    supplier_a = _create_supplier("Supplier A Buy")
    supplier_b = _create_supplier("Supplier B Buy")
    grn_a = _grn(supplier_a, quantity=10, unit_cost=30)  # 10*30 - 0 = 300
    _grn(supplier_b, quantity=5, unit_cost=20)  # 100

    # Return 2 units of supplier A's receipt linked to its GRN line.
    return_resp = client.post(
        "/api/v1/purchasing/purchase-returns",
        headers=headers,
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_a,
            "goods_receipt_id": grn_a["id"],
            "reason": "damaged in transit",
            "items": [
                {
                    "product_id": str(seeded_org["product"].id),
                    "quantity": 2,
                    "unit_cost": 30,
                    "original_grn_item_id": grn_a["items"][0]["id"],
                }
            ],
        },
    )
    assert return_resp.status_code == 201, return_resp.text
    return_total = return_resp.json()["return_total"]

    start, end = _today_range()
    resp = client.get(
        "/api/v1/reports/supplier-purchase-returns",
        headers=headers,
        params={"start": start, "end": end},
    )
    assert resp.status_code == 200, resp.text
    by_name = {row["supplier_name"]: row for row in resp.json()}

    a = by_name["Supplier A Buy"]
    assert a["purchase_count"] == 1
    assert a["purchase_value"] == 300.0
    assert a["return_count"] == 1
    assert a["return_value"] == return_total
    assert a["net_value"] == 300.0 - return_total

    b = by_name["Supplier B Buy"]
    assert b["purchase_value"] == 100.0
    assert b["return_count"] == 0
    assert b["return_value"] == 0.0
    assert b["net_value"] == 100.0


def test_supplier_purchase_return_ledger_is_daily_and_continuous(client, seeded_org):
    headers = seeded_org["auth_headers"]
    supplier_resp = client.post("/api/v1/party/suppliers", headers=headers, json={"name": "Ledger Supplier"})
    supplier_id = supplier_resp.json()["id"]

    grn_resp = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=headers,
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 7, "unit_cost": 40}],
        },
    )
    assert grn_resp.status_code == 201, grn_resp.text

    today = ist_today()
    start = (today - dt.timedelta(days=5)).isoformat()
    end = today.isoformat()
    resp = client.get(
        "/api/v1/reports/supplier-purchase-return-ledger",
        headers=headers,
        params={"supplier_id": supplier_id, "start": start, "end": end},
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    # Every calendar day in the range appears, so the ledger is continuous.
    assert len(rows) == 6
    assert sum(r["purchase_value"] for r in rows) == 280.0  # 7*40
    assert sum(r["return_value"] for r in rows) == 0.0
