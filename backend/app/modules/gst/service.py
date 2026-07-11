"""Pure GST calculation logic -- no DB, no FastAPI, no ORM.

Kept dependency-free deliberately: this is the single place GST math
happens (line tax split, invoice rounding), so it must be trivially
unit-testable and impossible to get subtly wrong in two different call
sites. Callers (sales/purchasing services) resolve the tax rate and
inter-state flag from the DB, then hand primitives in here.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


def _round2(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class LineTaxBreakdown:
    taxable_value: float
    tax_rate_percent: float
    cgst_amount: float
    sgst_amount: float
    igst_amount: float
    cess_amount: float
    line_total: float


def is_inter_state_supply(seller_state_code: str, buyer_state_code: str | None) -> bool:
    """Place-of-supply rule for POS retail: an unregistered/walk-in
    customer (no state code captured) is always treated as intra-state,
    since retail counter sales default to the seller's state as place of
    supply unless the customer explicitly provides a different billing/
    shipping state (e.g. a registered B2B customer)."""
    if not buyer_state_code:
        return False
    return seller_state_code != buyer_state_code


def compute_line_tax(
    quantity: float,
    unit_price: float,
    discount_amount: float,
    tax_rate_percent: float,
    is_inter_state: bool,
    cess_percent: float = 0,
) -> LineTaxBreakdown:
    """GST split for one invoice line.

    Intra-state: `tax_rate_percent` splits evenly into CGST + SGST.
    Inter-state: the full rate is charged as IGST.
    Rounding is applied once, on the final taxable value and each tax
    component (not on intermediate ratios), per standard GST invoicing
    practice.
    """
    if quantity < 0 or unit_price < 0 or discount_amount < 0 or tax_rate_percent < 0:
        raise ValueError("quantity, unit_price, discount_amount, tax_rate_percent must be non-negative")

    qty = Decimal(str(quantity))
    price = Decimal(str(unit_price))
    discount = Decimal(str(discount_amount))
    rate = Decimal(str(tax_rate_percent))
    cess_rate = Decimal(str(cess_percent))

    gross = qty * price
    taxable_value = gross - discount
    if taxable_value < 0:
        raise ValueError("discount_amount cannot exceed gross line value")

    tax_total = taxable_value * rate / Decimal(100)
    cess_amount = taxable_value * cess_rate / Decimal(100)

    if is_inter_state:
        cgst = Decimal(0)
        sgst = Decimal(0)
        igst = tax_total
    else:
        cgst = tax_total / 2
        sgst = tax_total / 2
        igst = Decimal(0)

    line_total = taxable_value + cgst + sgst + igst + cess_amount

    return LineTaxBreakdown(
        taxable_value=_round2(taxable_value),
        tax_rate_percent=float(rate),
        cgst_amount=_round2(cgst),
        sgst_amount=_round2(sgst),
        igst_amount=_round2(igst),
        cess_amount=_round2(cess_amount),
        line_total=_round2(line_total),
    )


def round_invoice_total(grand_total: float) -> tuple[float, float]:
    """Round the invoice grand total to the nearest rupee (standard Indian
    retail practice) and report the round-off adjustment separately so it
    can be shown as its own line and posted to a dedicated rounding ledger
    account rather than silently folded into sales value."""
    exact = Decimal(str(grand_total))
    rounded = exact.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    round_off = rounded - exact
    return float(rounded), _round2(round_off)
