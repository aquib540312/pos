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


def _complete_b2b_sale(client, seeded_org, customer_id):
    # No separate _receive_stock call: the caller already received enough
    # stock for both a B2B and a walk-in sale (see the b2b/b2cs split
    # test) -- receiving twice would violate the one-supplier-per-name
    # unique constraint _receive_stock relies on.
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
    return sale_resp.json()


def _current_return_period():
    import datetime as dt

    today = dt.date.today()
    return f"{today.month:02d}{today.year}"


def test_organization_without_gstin_is_rejected(client, seeded_org):
    period = _current_return_period()
    resp = client.post(f"/api/v1/gst-filing/gstr1/{period}/generate", headers=seeded_org["auth_headers"])
    # seeded_org fixture creates an org without a GSTIN configured
    assert resp.status_code == 422


def test_full_gstr1_generate_submit_status_flow_with_mock_gsp(client, seeded_org, db_session):
    _complete_sale(client, seeded_org)

    from app.models.organization import Organization

    org = db_session.get(Organization, seeded_org["organization"].id)
    org.gstin = "27AAAAA0000A1Z5"
    db_session.commit()

    period = _current_return_period()

    generate_resp = client.post(f"/api/v1/gst-filing/gstr1/{period}/generate", headers=seeded_org["auth_headers"])
    assert generate_resp.status_code == 200, generate_resp.text
    payload = generate_resp.json()
    assert payload["status"] == "generated"
    assert payload["payload"]["gstin"] == "27AAAAA0000A1Z5"
    assert payload["payload"]["hsn"]["data"][0]["hsn_sc"] == seeded_org["hsn"].code
    assert len(payload["payload"]["b2cs"]) == 1

    get_resp = client.get(f"/api/v1/gst-filing/gstr1/{period}", headers=seeded_org["auth_headers"])
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "generated"

    submit_resp = client.post(f"/api/v1/gst-filing/gstr1/{period}/submit", headers=seeded_org["auth_headers"])
    assert submit_resp.status_code == 200, submit_resp.text
    submitted = submit_resp.json()
    assert submitted["status"] == "filed"  # MockGSPAdapter reports "filed" immediately
    assert submitted["gsp_reference"] == f"MOCKGSP-27AAAAA0000A1Z5-{period}"
    assert submitted["filed_at"] is not None

    status_resp = client.get(f"/api/v1/gst-filing/gstr1/{period}/status", headers=seeded_org["auth_headers"])
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "filed"


def test_cannot_resubmit_a_filed_return(client, seeded_org, db_session):
    _complete_sale(client, seeded_org)
    from app.models.organization import Organization

    org = db_session.get(Organization, seeded_org["organization"].id)
    org.gstin = "27AAAAA0000A1Z5"
    db_session.commit()

    period = _current_return_period()
    client.post(f"/api/v1/gst-filing/gstr1/{period}/generate", headers=seeded_org["auth_headers"])
    client.post(f"/api/v1/gst-filing/gstr1/{period}/submit", headers=seeded_org["auth_headers"])

    second_submit = client.post(f"/api/v1/gst-filing/gstr1/{period}/submit", headers=seeded_org["auth_headers"])
    assert second_submit.status_code == 422

    second_generate = client.post(f"/api/v1/gst-filing/gstr1/{period}/generate", headers=seeded_org["auth_headers"])
    assert second_generate.status_code == 422


def test_invalid_return_period_format_is_rejected(client, seeded_org, db_session):
    from app.models.organization import Organization

    org = db_session.get(Organization, seeded_org["organization"].id)
    org.gstin = "27AAAAA0000A1Z5"
    db_session.commit()

    resp = client.post("/api/v1/gst-filing/gstr1/notaperiod/generate", headers=seeded_org["auth_headers"])
    assert resp.status_code == 422


def test_b2b_sale_is_reported_invoice_wise_and_excluded_from_b2cs(client, seeded_org, db_session):
    customer_resp = client.post(
        "/api/v1/party/customers",
        headers=seeded_org["auth_headers"],
        json={"name": "Registered Buyer Pvt Ltd", "gstin": "29BBBBB1111B1Z1", "state_code": "27"},
    )
    assert customer_resp.status_code == 201, customer_resp.text
    customer_id = customer_resp.json()["id"]

    _receive_stock(client, seeded_org, quantity=2)  # enough for both sales below
    _complete_b2b_sale(client, seeded_org, customer_id)  # ends up in b2b
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
    assert sale_resp.status_code == 201, sale_resp.text  # no customer -- ends up in b2cs

    from app.models.organization import Organization

    org = db_session.get(Organization, seeded_org["organization"].id)
    org.gstin = "27AAAAA0000A1Z5"
    db_session.commit()

    period = _current_return_period()
    generate_resp = client.post(f"/api/v1/gst-filing/gstr1/{period}/generate", headers=seeded_org["auth_headers"])
    assert generate_resp.status_code == 200, generate_resp.text
    payload = generate_resp.json()["payload"]

    assert len(payload["b2b"]) == 1
    assert payload["b2b"][0]["ctin"] == "29BBBBB1111B1Z1"
    assert len(payload["b2b"][0]["inv"]) == 1
    assert len(payload["b2cs"]) == 1  # only the walk-in sale, not the B2B one


def test_submit_without_generate_is_404(client, seeded_org, db_session):
    from app.models.organization import Organization

    org = db_session.get(Organization, seeded_org["organization"].id)
    org.gstin = "27AAAAA0000A1Z5"
    db_session.commit()

    resp = client.post("/api/v1/gst-filing/gstr1/012099/submit", headers=seeded_org["auth_headers"])
    assert resp.status_code == 404
