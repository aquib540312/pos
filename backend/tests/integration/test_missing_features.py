from datetime import date, timedelta

from app.models.catalog import ProductBatch


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


def _make_sale(client, seeded_org, quantity=2):
    grand = round(quantity * 40 * 1.18)
    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": quantity}],
            "payments": [{"method": "cash", "amount": grand}],
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text
    return sale_resp.json()


# --------------------------------------------------------------------------
# Catalog maintenance: product update / deactivate, reference-data updates
# --------------------------------------------------------------------------


def test_update_product_changes_fields(client, seeded_org):
    pid = str(seeded_org["product"].id)
    resp = client.patch(
        f"/api/v1/catalog/products/{pid}",
        headers=seeded_org["auth_headers"],
        json={"name": "Whole Wheat Bread", "sale_price": 45, "remove_barcode": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Whole Wheat Bread"
    assert body["sale_price"] == 45
    assert body["barcode"] is None


def test_update_product_duplicate_sku_rejected(client, seeded_org, db_session):
    from app.modules.catalog.service import CatalogService

    CatalogService(db_session).create_product(
        seeded_org["organization"].id, sku="OTHER-001", name="Other", uom_id=seeded_org["uom"].id,
        mrp=10, sale_price=10, hsn_code_id=seeded_org["hsn"].id,
    )
    db_session.commit()
    resp = client.patch(
        f"/api/v1/catalog/products/{seeded_org['product'].id}",
        headers=seeded_org["auth_headers"],
        json={"sku": "OTHER-001"},
    )
    assert resp.status_code == 409


def test_deactivate_product_hides_from_search(client, seeded_org):
    pid = str(seeded_org["product"].id)
    resp = client.patch(
        f"/api/v1/catalog/products/{pid}/deactivate", headers=seeded_org["auth_headers"]
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is False

    listing = client.get("/api/v1/catalog/products?search=White", headers=seeded_org["auth_headers"])
    assert listing.status_code == 200
    assert all(p["id"] != pid for p in listing.json())


def test_update_uom_and_hsn(client, seeded_org):
    uom_resp = client.patch(
        f"/api/v1/catalog/uom/{seeded_org['uom'].id}",
        headers=seeded_org["auth_headers"],
        json={"name": "Piece"},
    )
    assert uom_resp.status_code == 200, uom_resp.text
    assert uom_resp.json()["name"] == "Piece"

    hsn_resp = client.patch(
        f"/api/v1/catalog/hsn/{seeded_org['hsn'].id}",
        headers=seeded_org["auth_headers"],
        json={"rate_percent": 12},
    )
    assert hsn_resp.status_code == 200, hsn_resp.text
    assert hsn_resp.json()["current_rate_percent"] == 12

    uom_list = client.get("/api/v1/catalog/uom", headers=seeded_org["auth_headers"])
    assert any(u["id"] == str(seeded_org["uom"].id) and u["name"] == "Piece" for u in uom_list.json())


# --------------------------------------------------------------------------
# Party maintenance: customer/supplier update, credit collection
# --------------------------------------------------------------------------


def test_update_customer_and_collect_credit(client, seeded_org):
    customer_resp = client.post(
        "/api/v1/party/customers",
        headers=seeded_org["auth_headers"],
        json={"name": "Credit Joe", "is_credit_customer": True, "credit_limit": 1000, "credit_balance": 0},
    )
    assert customer_resp.status_code == 201
    cid = customer_resp.json()["id"]

    _receive_stock(client, seeded_org, quantity=100)
    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "customer_id": cid,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 2}],
            "payments": [],
            "is_credit_sale": True,
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text
    owed = sale_resp.json()["grand_total"]

    # Update the customer's credit limit.
    update_resp = client.patch(
        f"/api/v1/party/customers/{cid}",
        headers=seeded_org["auth_headers"],
        json={"credit_limit": 2000},
    )
    assert update_resp.status_code == 200, update_resp.text
    assert update_resp.json()["credit_limit"] == 2000

    # Collect the full outstanding balance.
    collect_resp = client.post(
        f"/api/v1/party/customers/{cid}/collect",
        headers=seeded_org["auth_headers"],
        json={"amount": owed, "method": "cash"},
    )
    assert collect_resp.status_code == 200, collect_resp.text
    assert collect_resp.json()["credit_balance"] == 0


def test_collect_more_than_owed_is_capped(client, seeded_org):
    customer_resp = client.post(
        "/api/v1/party/customers",
        headers=seeded_org["auth_headers"],
        json={"name": "Cap Joe", "is_credit_customer": True, "credit_limit": 1000},
    )
    cid = customer_resp.json()["id"]
    _receive_stock(client, seeded_org, quantity=100)
    client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "customer_id": cid,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1}],
            "payments": [],
            "is_credit_sale": True,
        },
    )
    resp = client.post(
        f"/api/v1/party/customers/{cid}/collect",
        headers=seeded_org["auth_headers"],
        json={"amount": 99999, "method": "cash"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["credit_balance"] == 0


def test_update_supplier(client, seeded_org):
    resp = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": "ACME Foods"}
    )
    sid = resp.json()["id"]
    update = client.patch(
        f"/api/v1/party/suppliers/{sid}",
        headers=seeded_org["auth_headers"],
        json={"phone": "9876543210", "remove_email": True},
    )
    assert update.status_code == 200, update.text
    assert update.json()["phone"] == "9876543210"


# --------------------------------------------------------------------------
# Sales: returns list/detail, invoice cancellation
# --------------------------------------------------------------------------


def test_list_returns_after_creating_one(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=100)
    invoice = _make_sale(client, seeded_org, quantity=4)
    item_id = invoice["items"][0]["id"]

    ret_resp = client.post(
        f"/api/v1/sales/returns?warehouse_id={seeded_org['warehouse'].id}",
        headers=seeded_org["auth_headers"],
        json={
            "original_invoice_id": invoice["id"],
            "reason": "changed mind",
            "items": [{"original_invoice_item_id": item_id, "quantity": 2}],
        },
    )
    assert ret_resp.status_code == 201, ret_resp.text
    ret_id = ret_resp.json()["id"]

    listing = client.get("/api/v1/sales/returns", headers=seeded_org["auth_headers"])
    assert listing.status_code == 200
    assert any(r["id"] == ret_id for r in listing.json())

    detail = client.get(f"/api/v1/sales/returns/{ret_id}", headers=seeded_org["auth_headers"])
    assert detail.status_code == 200
    assert detail.json()["reason"] == "changed mind"
    assert len(detail.json()["items"]) == 1


def test_cancel_invoice_restores_stock_and_marks_cancelled(client, seeded_org, db_session):
    _receive_stock(client, seeded_org, quantity=100)
    invoice = _make_sale(client, seeded_org, quantity=3)

    from app.models.inventory import StockItem

    stock = db_session.query(StockItem).filter_by(product_id=seeded_org["product"].id).one()
    assert float(stock.quantity_on_hand) == 97.0

    cancel_resp = client.post(
        f"/api/v1/sales/{invoice['id']}/cancel",
        headers=seeded_org["auth_headers"],
        json={"reason": "wrong product"},
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["status"] == "cancelled"

    db_session.expire_all()
    stock = db_session.query(StockItem).filter_by(product_id=seeded_org["product"].id).one()
    assert float(stock.quantity_on_hand) == 100.0


def test_cancel_invoice_with_return_is_rejected(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=100)
    invoice = _make_sale(client, seeded_org, quantity=4)
    item_id = invoice["items"][0]["id"]
    ret_resp = client.post(
        f"/api/v1/sales/returns?warehouse_id={seeded_org['warehouse'].id}",
        headers=seeded_org["auth_headers"],
        json={
            "original_invoice_id": invoice["id"],
            "items": [{"original_invoice_item_id": item_id, "quantity": 1}],
        },
    )
    assert ret_resp.status_code == 201, ret_resp.text

    cancel_resp = client.post(
        f"/api/v1/sales/{invoice['id']}/cancel",
        headers=seeded_org["auth_headers"],
        json={"reason": "nope"},
    )
    assert cancel_resp.status_code == 409


def test_cancel_credit_invoice_reverses_balance_and_loyalty(client, seeded_org):
    customer_resp = client.post(
        "/api/v1/party/customers",
        headers=seeded_org["auth_headers"],
        json={"name": "Cancel Credit", "is_credit_customer": True, "credit_limit": 5000},
    )
    cid = customer_resp.json()["id"]
    _receive_stock(client, seeded_org, quantity=100)
    sale_resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "customer_id": cid,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 2}],
            "payments": [],
            "is_credit_sale": True,
        },
    )
    assert sale_resp.status_code == 201, sale_resp.text

    customer = client.get(f"/api/v1/party/customers/{cid}", headers=seeded_org["auth_headers"]).json()
    assert customer["credit_balance"] == sale_resp.json()["grand_total"]

    cancel_resp = client.post(
        f"/api/v1/sales/{sale_resp.json()['id']}/cancel",
        headers=seeded_org["auth_headers"],
        json={"reason": "cancel credit"},
    )
    assert cancel_resp.status_code == 200, cancel_resp.text

    customer = client.get(f"/api/v1/party/customers/{cid}", headers=seeded_org["auth_headers"]).json()
    assert customer["credit_balance"] == 0


# --------------------------------------------------------------------------
# Reports: expiring stock, low stock, valuation, dashboard
# --------------------------------------------------------------------------


def test_expiring_stock_report(client, seeded_org, db_session):
    _receive_stock(client, seeded_org, quantity=50)
    batch = db_session.query(ProductBatch).filter_by(product_id=seeded_org["product"].id).one()
    batch.expiry_date = date.today() + timedelta(days=5)
    db_session.commit()

    resp = client.get("/api/v1/reports/expiring-stock?within_days=30", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200
    assert any(r["product_id"] == str(seeded_org["product"].id) for r in resp.json())
    row = next(r for r in resp.json() if r["product_id"] == str(seeded_org["product"].id))
    assert row["days_to_expiry"] == 5


def test_low_stock_report(client, seeded_org):
    # Product reorder level is 10, and no stock exists initially.
    resp = client.get("/api/v1/reports/low-stock", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200
    assert any(r["product_id"] == str(seeded_org["product"].id) for r in resp.json())


def test_stock_valuation_report(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=100, unit_cost=30)
    resp = client.get("/api/v1/reports/stock-valuation", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200
    rows = [r for r in resp.json() if r["product_id"] == str(seeded_org["product"].id)]
    assert len(rows) == 1
    assert rows[0]["valuation"] == 3000.0


def test_stock_ledger_history(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=100)
    _make_sale(client, seeded_org, quantity=2)

    resp = client.get(
        f"/api/v1/reports/stock-ledger?product_id={seeded_org['product'].id}",
        headers=seeded_org["auth_headers"],
    )
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 2  # a purchase_receipt + a sale
    assert {r["movement_type"] for r in rows} >= {"purchase_receipt", "sale"}


def test_dashboard_stats(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=100)
    _make_sale(client, seeded_org, quantity=2)

    resp = client.get("/api/v1/reports/dashboard", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["today_invoice_count"] == 1
    assert body["today_grand_total"] > 0
    assert body["open_shifts"] == 0


# --------------------------------------------------------------------------
# Auth: change password
# --------------------------------------------------------------------------


def test_change_password_flow(client, seeded_org):
    wrong = client.post(
        "/api/v1/auth/change-password",
        headers=seeded_org["auth_headers"],
        json={"current_password": "WrongPass123!", "new_password": "NewPass456!"},
    )
    assert wrong.status_code == 401

    ok = client.post(
        "/api/v1/auth/change-password",
        headers=seeded_org["auth_headers"],
        json={"current_password": "TestPass123!", "new_password": "NewPass456!"},
    )
    assert ok.status_code == 200, ok.text

    # Old password no longer works.
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "TestPass123!"},
    )
    assert login.status_code == 401
    login = client.post(
        "/api/v1/auth/login",
        data={"username": "admin@test.local", "password": "NewPass456!"},
    )
    assert login.status_code == 200


# --------------------------------------------------------------------------
# Loyalty: coupon / gift-card listing and deactivation
# --------------------------------------------------------------------------


def test_list_and_deactivate_coupon_and_gift_card(client, seeded_org):
    from datetime import date

    coupon_resp = client.post(
        "/api/v1/loyalty/coupons",
        headers=seeded_org["auth_headers"],
        json={
            "code": "SAVE10", "discount_type": "percent", "discount_value": 10,
            "valid_from": str(date.today()), "min_order_value": 0,
        },
    )
    assert coupon_resp.status_code == 201, coupon_resp.text
    coupon_id = coupon_resp.json()["id"]

    card_resp = client.post(
        "/api/v1/loyalty/gift-cards",
        headers=seeded_org["auth_headers"],
        json={"card_number": "GC-0001", "initial_value": 500},
    )
    assert card_resp.status_code == 201, card_resp.text
    card_id = card_resp.json()["id"]

    coupon_list = client.get("/api/v1/loyalty/coupons", headers=seeded_org["auth_headers"])
    assert any(c["id"] == coupon_id for c in coupon_list.json())

    card_list = client.get("/api/v1/loyalty/gift-cards", headers=seeded_org["auth_headers"])
    assert any(c["id"] == card_id for c in card_list.json())

    deact = client.patch(
        f"/api/v1/loyalty/coupons/{coupon_id}/deactivate", headers=seeded_org["auth_headers"]
    )
    assert deact.status_code == 200
    assert deact.json()["is_active"] is False

    card_deact = client.patch(
        f"/api/v1/loyalty/gift-cards/{card_id}/deactivate", headers=seeded_org["auth_headers"]
    )
    assert card_deact.status_code == 200
    assert card_deact.json()["is_active"] is False


# --------------------------------------------------------------------------
# Purchasing: pending-GRN view, PO status transitions, purchase returns
# --------------------------------------------------------------------------


def _create_purchase_order(client, seeded_org, supplier_id, quantity=50):
    resp = client.post(
        "/api/v1/purchasing/purchase-orders",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "supplier_id": supplier_id,
            "order_date": "2026-01-01",
            "items": [
                {"product_id": str(seeded_org["product"].id), "quantity_ordered": quantity, "unit_cost": 30}
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_pending_grn_lists_under_delivered_lines(client, seeded_org):
    supplier = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": "GRN Foods"}
    ).json()
    po = _create_purchase_order(client, seeded_org, supplier["id"], quantity=40)

    pending = client.get("/api/v1/purchasing/purchase-orders/pending", headers=seeded_org["auth_headers"])
    assert pending.status_code == 200, pending.text
    rows = [r for r in pending.json() if r["po_id"] == po["id"]]
    assert len(rows) == 1
    assert rows[0]["outstanding_quantity"] == 40

    # Partially deliver 15 -> 25 still owed, and the PO remains in the list.
    client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier["id"],
            "purchase_order_id": po["id"],
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 15, "unit_cost": 30}],
        },
    )
    pending2 = client.get("/api/v1/purchasing/purchase-orders/pending", headers=seeded_org["auth_headers"]).json()
    row2 = next(r for r in pending2 if r["po_id"] == po["id"])
    assert row2["quantity_received"] == 15
    assert row2["outstanding_quantity"] == 25


def test_pending_grn_excludes_fully_received_po(client, seeded_org):
    supplier = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": "GRN Done"}
    ).json()
    po = _create_purchase_order(client, seeded_org, supplier["id"], quantity=10)
    client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier["id"],
            "purchase_order_id": po["id"],
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 10, "unit_cost": 30}],
        },
    )
    pending = client.get("/api/v1/purchasing/purchase-orders/pending", headers=seeded_org["auth_headers"]).json()
    assert all(r["po_id"] != po["id"] for r in pending)


def test_po_status_transition_and_invalid_move(client, seeded_org):
    supplier = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": "Status Foods"}
    ).json()
    po = _create_purchase_order(client, seeded_org, supplier["id"])
    po_id = po["id"]
    # POs are created in 'submitted' state (draft POs are created via the
    # API without a draft option today).

    # submitted -> closed (valid)
    closed = client.patch(
        f"/api/v1/purchasing/purchase-orders/{po_id}/status",
        headers=seeded_org["auth_headers"],
        json={"status": "closed"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["status"] == "closed"

    # closed -> submitted (invalid transition)
    bad = client.patch(
        f"/api/v1/purchasing/purchase-orders/{po_id}/status",
        headers=seeded_org["auth_headers"],
        json={"status": "submitted"},
    )
    assert bad.status_code == 409


def test_purchase_return_reduces_supplier_payable_and_stock(client, seeded_org):
    supplier = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": "Ret Foods"}
    ).json()
    grn = client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier["id"],
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 20, "unit_cost": 30}],
        },
    ).json()
    grn_item = grn["items"][0]

    stock_before = sum(
        s["quantity_on_hand"]
        for s in client.get(
            "/api/v1/inventory/stock",
            headers=seeded_org["auth_headers"],
            params={"warehouse_id": str(seeded_org["warehouse"].id)},
        ).json()
        if s["product_id"] == str(seeded_org["product"].id)
    )

    ret = client.post(
        "/api/v1/purchasing/purchase-returns",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier["id"],
            "reason": "defective",
            "items": [
                {
                    "product_id": str(seeded_org["product"].id),
                    "quantity": 5,
                    "unit_cost": 30,
                    "original_grn_item_id": grn_item["id"],
                }
            ],
        },
    )
    assert ret.status_code == 201, ret.text
    body = ret.json()
    assert body["return_total"] > 0
    assert len(body["items"]) == 1

    suppliers = client.get("/api/v1/party/suppliers", headers=seeded_org["auth_headers"]).json()
    payable = next(s["payable_balance"] for s in suppliers if s["id"] == supplier["id"])
    assert payable == round(20 * 30 * 1.18 - 5 * 30 * 1.18, 2)

    stock_after = sum(
        s["quantity_on_hand"]
        for s in client.get(
            "/api/v1/inventory/stock",
            headers=seeded_org["auth_headers"],
            params={"warehouse_id": str(seeded_org["warehouse"].id)},
        ).json()
        if s["product_id"] == str(seeded_org["product"].id)
    )
    assert stock_after == stock_before - 5

    listing = client.get("/api/v1/purchasing/purchase-returns", headers=seeded_org["auth_headers"]).json()
    assert any(r["id"] == body["id"] for r in listing)


# --------------------------------------------------------------------------
# Party: supplier payments reduce payable balance and post a ledger entry
# --------------------------------------------------------------------------


def test_supplier_payment_reduces_payable_and_creates_ledger_entry(client, seeded_org, db_session):
    from app.models.accounting import JournalEntry

    supplier_resp = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": "Pay Foods"}
    )
    supplier_id = supplier_resp.json()["id"]
    client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier_id,
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 10, "unit_cost": 30}],
        },
    )
    suppliers = client.get("/api/v1/party/suppliers", headers=seeded_org["auth_headers"]).json()
    payable_before = next(s["payable_balance"] for s in suppliers if s["id"] == supplier_id)

    pay = client.post(
        f"/api/v1/party/suppliers/{supplier_id}/pay",
        headers=seeded_org["auth_headers"],
        json={"amount": 100, "method": "bank", "reference": "RTGS-1"},
    )
    assert pay.status_code == 200, pay.text
    assert pay.json()["amount"] == 100
    assert pay.json()["outstanding_payable"] == round(payable_before - 100, 2)

    suppliers = client.get("/api/v1/party/suppliers", headers=seeded_org["auth_headers"]).json()
    assert next(s["payable_balance"] for s in suppliers if s["id"] == supplier_id) == round(payable_before - 100, 2)

    payments = client.get(
        f"/api/v1/party/suppliers/{supplier_id}/payments", headers=seeded_org["auth_headers"]
    )
    assert payments.status_code == 200, payments.text
    assert len(payments.json()) == 1
    assert payments.json()[0]["reference"] == "RTGS-1"

    entry = (
        db_session.query(JournalEntry).filter_by(reference_type="supplier_payment").one()
    )
    assert entry is not None


def test_supplier_payment_capped_at_payable(client, seeded_org):
    supplier = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": "Cap Foods"}
    ).json()
    client.post(
        "/api/v1/purchasing/goods-receipts",
        headers=seeded_org["auth_headers"],
        json={
            "warehouse_id": str(seeded_org["warehouse"].id),
            "supplier_id": supplier["id"],
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": 4, "unit_cost": 30}],
        },
    )
    suppliers = client.get("/api/v1/party/suppliers", headers=seeded_org["auth_headers"]).json()
    payable = next(s["payable_balance"] for s in suppliers if s["id"] == supplier["id"])

    pay = client.post(
        f"/api/v1/party/suppliers/{supplier['id']}/pay",
        headers=seeded_org["auth_headers"],
        json={"amount": 99999, "method": "cash"},
    )
    assert pay.status_code == 200, pay.text
    # Capped at the outstanding balance -- no negative payable allowed.
    assert pay.json()["amount"] == payable
    assert pay.json()["outstanding_payable"] == 0


def test_supplier_payment_with_no_payable_returns_404(client, seeded_org):
    supplier = client.post(
        "/api/v1/party/suppliers", headers=seeded_org["auth_headers"], json={"name": "NoPay Foods"}
    ).json()
    pay = client.post(
        f"/api/v1/party/suppliers/{supplier['id']}/pay",
        headers=seeded_org["auth_headers"],
        json={"amount": 50, "method": "cash"},
    )
    assert pay.status_code == 404


# --------------------------------------------------------------------------
# In-app notifications: dashboard alerts land in the inbox, mark-read works,
# and alert creation is idempotent across dashboard reloads.
# --------------------------------------------------------------------------


def test_dashboard_load_creates_low_stock_notification(client, seeded_org, db_session):
    from app.models.notifications import AppNotification

    # The seeded product has reorder_level=10 and zero stock on hand.
    dash = client.get("/api/v1/reports/dashboard", headers=seeded_org["auth_headers"])
    assert dash.status_code == 200, dash.text
    assert dash.json()["low_stock_count"] >= 1

    rows = db_session.query(AppNotification).filter_by(category="low_stock").all()
    assert len(rows) >= 1
    assert any(r.reference_id == seeded_org["product"].id for r in rows)

    # Reloading the dashboard must not duplicate the alert.
    client.get("/api/v1/reports/dashboard", headers=seeded_org["auth_headers"])
    db_session.expire_all()
    assert db_session.query(AppNotification).filter_by(category="low_stock").count() == len(rows)


def test_notifications_list_unread_count_and_mark_read(client, seeded_org, db_session):
    from app.models.notifications import AppNotification

    client.get("/api/v1/reports/dashboard", headers=seeded_org["auth_headers"])
    first = db_session.query(AppNotification).filter_by(category="low_stock").first()

    listing = client.get("/api/v1/notifications", headers=seeded_org["auth_headers"])
    assert listing.status_code == 200, listing.text
    assert any(n["id"] == str(first.id) for n in listing.json())

    unread = client.get("/api/v1/notifications/unread-count", headers=seeded_org["auth_headers"])
    assert unread.status_code == 200, unread.text
    assert unread.json()["unread_count"] >= 1

    marked = client.post(
        f"/api/v1/notifications/{first.id}/read", headers=seeded_org["auth_headers"]
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["is_read"] is True

    unread2 = client.get("/api/v1/notifications/unread-count", headers=seeded_org["auth_headers"])
    assert unread2.json()["unread_count"] == max(0, unread.json()["unread_count"] - 1)


def test_mark_all_read_clears_inbox(client, seeded_org, db_session):
    from app.models.notifications import AppNotification

    client.get("/api/v1/reports/dashboard", headers=seeded_org["auth_headers"])
    total = db_session.query(AppNotification).filter_by(is_read=False).count()
    assert total >= 1

    resp = client.post("/api/v1/notifications/read-all", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200, resp.text
    assert resp.json()["marked"] == total

    unread = client.get("/api/v1/notifications/unread-count", headers=seeded_org["auth_headers"])
    assert unread.json()["unread_count"] == 0
