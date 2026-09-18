from escpos.printer import Dummy

from app.modules.printing.receipt_builder import render_receipt


def _sample_invoice():
    return {
        "invoice_number": "INV/2026/000001",
        "invoice_date": "11-Jul-2026 10:00",
        "items": [
            {"product_name": "White Bread 400g", "quantity": 2, "unit_price": 40.0, "line_total": 94.4},
        ],
        "taxable_total": 80.0,
        "cgst_total": 7.2,
        "sgst_total": 7.2,
        "igst_total": 0.0,
        "coupon_code": None,
        "coupon_discount_amount": 0,
        "round_off": -0.2,
        "grand_total": 94.0,
        "payments": [{"method": "cash", "amount": 94.0}],
    }


def test_render_receipt_produces_nonempty_escpos_bytes():
    printer = Dummy()
    render_receipt(printer, _sample_invoice())
    assert len(printer.output) > 0


def test_render_receipt_includes_expected_text_content():
    printer = Dummy()
    render_receipt(printer, _sample_invoice())
    text = printer.output.decode("latin1")
    assert "TAX INVOICE" in text
    assert "INV/2026/000001" in text
    assert "White Bread 400g" in text
    assert "94.00" in text  # grand total
    assert "CASH" in text


def test_render_receipt_ends_with_cut_command():
    printer = Dummy()
    render_receipt(printer, _sample_invoice())
    # GS V (cut) is \x1d\x56 per the ESC/POS spec
    assert b"\x1dV" in printer.output


def test_render_receipt_shows_coupon_line_when_present():
    invoice = _sample_invoice()
    invoice["coupon_code"] = "SAVE10"
    invoice["coupon_discount_amount"] = 10.0
    printer = Dummy()
    render_receipt(printer, invoice)
    text = printer.output.decode("latin1")
    assert "SAVE10" in text


def test_render_receipt_shows_business_header_and_footer():
    invoice = _sample_invoice()
    invoice["business"] = {
        "legal_name": "Acme Trading Pvt Ltd",
        "trade_name": "Acme Mart",
        "gstin": "27AAAAA0000A1Z5",
        "address": "12 MG Road, Mumbai 400001",
        "phone": "+91 98200 12345",
    }
    invoice["footer_note"] = "No returns after 7 days."
    printer = Dummy()
    render_receipt(printer, invoice)
    text = printer.output.decode("latin1")
    assert "Acme Mart" in text
    assert "VAT: 27AAAAA0000A1Z5" in text
    assert "Tel: +91 98200 12345" in text
    assert "No returns after 7 days." in text


def test_render_receipt_without_business_falls_back_to_thanks_note():
    printer = Dummy()
    render_receipt(printer, _sample_invoice())
    text = printer.output.decode("latin1")
    assert "Thank you" in text
