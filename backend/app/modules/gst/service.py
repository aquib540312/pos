"""Saudi VAT calculation logic -- no DB, no FastAPI, no ORM.

Kept dependency-free deliberately: this is the single place VAT math
happens (line tax, invoice rounding), so it must be trivially
unit-testable and impossible to get subtly wrong in two different call
sites. Callers (sales/purchasing services) resolve the tax rate from
the DB, then hand primitives in here.

Saudi Arabia uses a flat 15% VAT rate (no CGST/SGST/IGST split).
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# Saudi Arabia VAT rate
SAUDI_VAT_RATE = 15.0


def _round2(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class LineTaxBreakdown:
    taxable_value: float
    tax_rate_percent: float
    vat_amount: float
    line_total: float


def compute_line_tax(
    quantity: float,
    unit_price: float,
    discount_amount: float,
    tax_rate_percent: float = SAUDI_VAT_RATE,
    is_inter_state: bool = False,  # Not used in Saudi VAT, kept for compatibility
    cess_percent: float = 0,  # Not used in Saudi VAT, kept for compatibility
) -> LineTaxBreakdown:
    """VAT calculation for one invoice line.

    Saudi Arabia uses a flat VAT rate (currently 15%) on taxable goods.
    No CGST/SGST/IGST split like Indian GST.
    Rounding is applied once, on the final taxable value and tax amount.
    """
    if quantity < 0 or unit_price < 0 or discount_amount < 0 or tax_rate_percent < 0:
        raise ValueError("quantity, unit_price, discount_amount, tax_rate_percent must be non-negative")

    qty = Decimal(str(quantity))
    price = Decimal(str(unit_price))
    discount = Decimal(str(discount_amount))
    rate = Decimal(str(tax_rate_percent))

    gross = qty * price
    taxable_value = gross - discount
    if taxable_value < 0:
        raise ValueError("discount_amount cannot exceed gross line value")

    vat_amount = taxable_value * rate / Decimal(100)
    line_total = taxable_value + vat_amount

    return LineTaxBreakdown(
        taxable_value=_round2(taxable_value),
        tax_rate_percent=float(rate),
        vat_amount=_round2(vat_amount),
        line_total=_round2(line_total),
    )


def round_money(value: float) -> float:
    """Round a monetary amount to 2 decimals, round-half-up. This is the
    single money-rounding rule for the whole app: invoice tax values and
    quotation line/grand totals must agree to the halala, and Python's
    built-in round() rounds half-to-even ("banker's"), which would make a
    quotation silently differ from the invoice it converts into."""
    return _round2(Decimal(str(value)))


def round_invoice_total(grand_total: float) -> tuple[float, float]:
    """Round the invoice grand total to the nearest SAR (standard Saudi
    retail practice) and report the round-off adjustment separately so it
    can be shown as its own line and posted to a dedicated rounding ledger
    account rather than silently folded into sales value."""
    exact = Decimal(str(grand_total))
    rounded = exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    round_off = rounded - exact
    return float(rounded), _round2(round_off)
