import datetime as dt


def _receive_stock(client, seeded_org, quantity=100, unit_cost=30):
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
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": quantity, "unit_cost": unit_cost}],
        },
    )
    assert grn_resp.status_code == 201, grn_resp.text
    return supplier_id


def _sell(client, seeded_org, quantity, amount):
    resp = client.post(
        "/api/v1/sales",
        headers=seeded_org["auth_headers"],
        json={
            "branch_id": str(seeded_org["branch"].id),
            "warehouse_id": str(seeded_org["warehouse"].id),
            "items": [{"product_id": str(seeded_org["product"].id), "quantity": quantity}],
            "payments": [{"method": "cash", "amount": amount}],
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _today_range():
    today = dt.date.today().isoformat()
    return today, today


def test_goods_receipt_updates_supplier_payable_and_ledger(client, seeded_org, db_session):
    supplier_id = _receive_stock(client, seeded_org, quantity=10, unit_cost=30)

    from app.models.accounting import JournalEntry, JournalLine, LedgerAccount
    from app.models.party import Supplier

    supplier = db_session.get(Supplier, supplier_id)
    assert float(supplier.payable_balance) == 300.0

    entry = db_session.query(JournalEntry).filter_by(reference_type="goods_receipt").one()
    lines = db_session.query(JournalLine).filter_by(entry_id=entry.id).all()
    by_code = {db_session.get(LedgerAccount, line.account_id).code: (line.debit, line.credit) for line in lines}
    assert by_code["1200"] == (300.0, 0.0)  # Inventory debited
    assert by_code["2000"] == (0.0, 300.0)  # Accounts Payable credited


def test_sale_and_return_post_balanced_journal_entries(client, seeded_org, db_session):
    _receive_stock(client, seeded_org, quantity=10, unit_cost=30)
    invoice = _sell(client, seeded_org, quantity=4, amount=189)  # 4*40=160 taxable, 18% => 28.8 tax => 188.8 -> 189

    invoice_item_id = invoice["items"][0]["id"]
    return_resp = client.post(
        f"/api/v1/sales/returns?warehouse_id={seeded_org['warehouse'].id}",
        headers=seeded_org["auth_headers"],
        json={
            "original_invoice_id": invoice["id"],
            "items": [{"original_invoice_item_id": invoice_item_id, "quantity": 2}],
        },
    )
    assert return_resp.status_code == 201, return_resp.text

    from app.models.accounting import JournalEntry, JournalLine

    for reference_type in ("sales_invoice", "sales_return"):
        entry = db_session.query(JournalEntry).filter_by(reference_type=reference_type).one()
        lines = db_session.query(JournalLine).filter_by(entry_id=entry.id).all()
        total_debit = round(sum(float(line.debit) for line in lines), 2)
        total_credit = round(sum(float(line.credit) for line in lines), 2)
        assert total_debit == total_credit, f"{reference_type} entry is unbalanced: {total_debit} != {total_credit}"


def test_profit_and_loss_reflects_sale(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=10, unit_cost=30)
    _sell(client, seeded_org, quantity=2, amount=94)  # 2*40=80 taxable, 18% => 14.4 tax => 94.4 -> 94

    start, end = _today_range()
    resp = client.get(
        "/api/v1/reports/profit-and-loss", headers=seeded_org["auth_headers"], params={"start": start, "end": end}
    )
    assert resp.status_code == 200, resp.text
    pl = resp.json()
    assert pl["total_income"] > 0
    sales_line = next(line for line in pl["income_lines"] if line["account_code"] == "4000")
    assert sales_line["amount"] == 80.0  # taxable value, net of GST


def test_balance_sheet_balances(client, seeded_org):
    _receive_stock(client, seeded_org, quantity=10, unit_cost=30)
    _sell(client, seeded_org, quantity=2, amount=94)

    as_of = dt.date.today().isoformat()
    resp = client.get("/api/v1/reports/balance-sheet", headers=seeded_org["auth_headers"], params={"as_of": as_of})
    assert resp.status_code == 200, resp.text
    bs = resp.json()
    assert round(bs["total_assets"], 2) == round(bs["total_liabilities"] + bs["total_equity"], 2)
