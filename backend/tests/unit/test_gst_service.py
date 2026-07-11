import pytest

from app.modules.gst.service import compute_line_tax, is_inter_state_supply, round_invoice_total


def test_intra_state_splits_cgst_sgst_evenly():
    result = compute_line_tax(
        quantity=2, unit_price=100, discount_amount=10, tax_rate_percent=18, is_inter_state=False
    )
    assert result.taxable_value == 190.0
    assert result.cgst_amount == 17.1
    assert result.sgst_amount == 17.1
    assert result.igst_amount == 0.0
    assert result.line_total == 224.2


def test_inter_state_charges_full_rate_as_igst():
    result = compute_line_tax(
        quantity=2, unit_price=100, discount_amount=10, tax_rate_percent=18, is_inter_state=True
    )
    assert result.cgst_amount == 0.0
    assert result.sgst_amount == 0.0
    assert result.igst_amount == 34.2
    assert result.line_total == 224.2


def test_cess_is_added_on_top_of_gst():
    result = compute_line_tax(
        quantity=1, unit_price=1000, discount_amount=0, tax_rate_percent=28, is_inter_state=False, cess_percent=12
    )
    assert result.cess_amount == 120.0
    assert result.line_total == 1000 + 280 + 120


def test_discount_exceeding_gross_value_raises():
    with pytest.raises(ValueError):
        compute_line_tax(quantity=1, unit_price=50, discount_amount=100, tax_rate_percent=18, is_inter_state=False)


def test_negative_inputs_rejected():
    with pytest.raises(ValueError):
        compute_line_tax(quantity=-1, unit_price=50, discount_amount=0, tax_rate_percent=18, is_inter_state=False)


@pytest.mark.parametrize(
    "seller,buyer,expected",
    [
        ("27", "27", False),
        ("27", "29", True),
        ("27", None, False),
    ],
)
def test_is_inter_state_supply(seller, buyer, expected):
    assert is_inter_state_supply(seller, buyer) is expected


@pytest.mark.parametrize(
    "amount,rounded,round_off",
    [
        (199.4, 199.0, -0.4),
        (199.5, 200.0, 0.5),
        (200.0, 200.0, 0.0),
        (200.01, 200.0, -0.01),
    ],
)
def test_round_invoice_total(amount, rounded, round_off):
    got_rounded, got_round_off = round_invoice_total(amount)
    assert got_rounded == rounded
    assert got_round_off == round_off
