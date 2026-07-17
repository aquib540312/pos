from app.modules.gst_filing.schema_builder import (
    B2BInvoiceLine,
    B2BInvoiceRateItem,
    B2CSLine,
    HSNSummaryLine,
    build_gstr1_json,
)


def test_gstr1_json_has_expected_top_level_shape():
    payload = build_gstr1_json("27AAAAA0000A1Z5", "072026", 1000.0, [], [])
    assert payload["gstin"] == "27AAAAA0000A1Z5"
    assert payload["fp"] == "072026"
    assert payload["gt"] == 1000.0
    assert "hsn" in payload and "data" in payload["hsn"]
    assert "b2cs" in payload


def test_hsn_section_maps_fields_correctly():
    hsn_lines = [
        HSNSummaryLine(
            hsn_code="1905", tax_rate_percent=18.0, taxable_value=100.0, cgst=9.0, sgst=9.0, igst=0.0, cess=0.0,
            invoice_count=1,
        )
    ]
    payload = build_gstr1_json("27AAAAA0000A1Z5", "072026", 118.0, hsn_lines, [])
    row = payload["hsn"]["data"][0]
    assert row["hsn_sc"] == "1905"
    assert row["txval"] == 100.0
    assert row["camt"] == 9.0
    assert row["samt"] == 9.0
    assert row["iamt"] == 0.0
    assert row["val"] == 118.0
    assert row["num"] == 1


def test_b2cs_section_marks_inter_vs_intra_state():
    b2cs_lines = [
        B2CSLine(
            place_of_supply_state_code="27", is_inter_state=False, tax_rate_percent=18.0,
            taxable_value=100.0, cgst=9.0, sgst=9.0, igst=0.0, cess=0.0,
        ),
        B2CSLine(
            place_of_supply_state_code="29", is_inter_state=True, tax_rate_percent=18.0,
            taxable_value=50.0, cgst=0.0, sgst=0.0, igst=9.0, cess=0.0,
        ),
    ]
    payload = build_gstr1_json("27AAAAA0000A1Z5", "072026", 168.0, [], b2cs_lines)
    intra, inter = payload["b2cs"]
    assert intra["sply_ty"] == "INTRA"
    assert intra["pos"] == "27"
    assert inter["sply_ty"] == "INTER"
    assert inter["iamt"] == 9.0


def test_b2b_section_groups_by_buyer_gstin_then_invoice_then_rate():
    b2b_lines = [
        B2BInvoiceLine(
            buyer_gstin="29BBBBB1111B1Z1",
            invoice_number="INV-1",
            invoice_date="17-07-2026",
            invoice_value=354.0,
            place_of_supply_state_code="27",
            is_inter_state=False,
            rate_items=[
                B2BInvoiceRateItem(tax_rate_percent=18.0, taxable_value=300.0, cgst=27.0, sgst=27.0, igst=0.0, cess=0.0),
                B2BInvoiceRateItem(tax_rate_percent=5.0, taxable_value=0.0, cgst=0.0, sgst=0.0, igst=0.0, cess=0.0),
            ],
        ),
        B2BInvoiceLine(
            buyer_gstin="29BBBBB1111B1Z1",
            invoice_number="INV-2",
            invoice_date="17-07-2026",
            invoice_value=118.0,
            place_of_supply_state_code="27",
            is_inter_state=False,
            rate_items=[
                B2BInvoiceRateItem(tax_rate_percent=18.0, taxable_value=100.0, cgst=9.0, sgst=9.0, igst=0.0, cess=0.0),
            ],
        ),
    ]
    payload = build_gstr1_json("27AAAAA0000A1Z5", "072026", 472.0, [], [], b2b_lines)

    assert len(payload["b2b"]) == 1  # one entry per distinct buyer GSTIN
    ctin_entry = payload["b2b"][0]
    assert ctin_entry["ctin"] == "29BBBBB1111B1Z1"
    assert len(ctin_entry["inv"]) == 2  # two invoices for that buyer

    first_invoice = ctin_entry["inv"][0]
    assert first_invoice["inum"] == "INV-1"
    assert first_invoice["val"] == 354.0
    assert len(first_invoice["itms"]) == 2  # two rate slabs on one invoice
    assert first_invoice["itms"][0]["itm_det"]["rt"] == 18.0
    assert first_invoice["itms"][0]["itm_det"]["camt"] == 27.0


def test_b2b_section_defaults_to_empty_when_omitted():
    payload = build_gstr1_json("27AAAAA0000A1Z5", "072026", 0.0, [], [])
    assert payload["b2b"] == []
