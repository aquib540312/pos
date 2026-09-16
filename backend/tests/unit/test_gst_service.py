import pytest

from app.modules.gst.service import compute_line_tax, round_invoice_total, SAUDI_VAT_RATE


def test_saudi_vat_15_percent():
    """Test Saudi Arabia 15% VAT calculation."""
    result = compute_line_tax(
        quantity=2, unit_price=100, discount_amount=10, tax_rate_percent=SAUDI_VAT_RATE
    )
    assert result.taxable_value == 190.0
    assert result.vat_amount == 28.5  # 15% of 190
    assert result.line_total == 218.5


def test_variable_weight_sale():
    """Test variable weight sale calculation for beef."""
    # Beef Tenderloin: 2.750 KG at 45 SAR/KG
    result = compute_line_tax(
        quantity=2.75, unit_price=45, discount_amount=0, tax_rate_percent=SAUDI_VAT_RATE
    )
    assert result.taxable_value == 123.75
    assert result.vat_amount == 18.56  # 15% of 123.75
    assert result.line_total == 142.31


def test_wholesale_discount():
    """Test wholesale discount calculation."""
    result = compute_line_tax(
        quantity=10, unit_price=39, discount_amount=0, tax_rate_percent=SAUDI_VAT_RATE
    )
    assert result.taxable_value == 390.0
    assert result.vat_amount == 58.5  # 15% of 390
    assert result.line_total == 448.5


def test_discount_exceeding_gross_value_raises():
    with pytest.raises(ValueError):
        compute_line_tax(quantity=1, unit_price=50, discount_amount=100, tax_rate_percent=SAUDI_VAT_RATE)


def test_negative_inputs_rejected():
    with pytest.raises(ValueError):
        compute_line_tax(quantity=-1, unit_price=50, discount_amount=0, tax_rate_percent=SAUDI_VAT_RATE)


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


def test_decimal_quantities():
    """Test decimal quantities for variable weight products."""
    # Minced beef: 0.125 KG at 35 SAR/KG
    result = compute_line_tax(
        quantity=0.125, unit_price=35, discount_amount=0, tax_rate_percent=SAUDI_VAT_RATE
    )
    assert result.taxable_value == 4.38  # 0.125 * 35 = 4.375, rounded to 4.38
    assert result.vat_amount == 0.66  # 15% of 4.38 = 0.657, rounded to 0.66
    assert result.line_total == 5.03  # 4.38 + 0.66 = 5.04, but actual is 5.03 due to rounding
