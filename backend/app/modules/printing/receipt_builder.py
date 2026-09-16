"""Renders a sales invoice onto an ESC/POS printer stream.

Takes any python-escpos printer instance (`escpos.printer.Dummy` for
tests/preview, `escpos.printer.Network` for a real Epson TM-series
printer on the LAN, `escpos.printer.Usb` for a USB-attached one) --
python-escpos's classes all implement the same command interface
(`.set()`, `.text()`, `.cut()`, ...), which is what makes this function
hardware-agnostic and fully testable without a physical printer: every
Epson ESC/POS-compatible printer speaks the same command set regardless
of transport (network socket, USB, serial), so swapping `Network(...)`
for real hardware is the only thing that changes going from dev to
production.
"""

from typing import Any, Protocol


class EscposPrinter(Protocol):
    def set(self, **kwargs: Any) -> None: ...
    def text(self, text: str) -> None: ...
    def cut(self) -> None: ...


def render_receipt(printer: EscposPrinter, invoice: dict) -> None:
    business = invoice.get("business")
    if business:
        business_name = business.get("trade_name") or business.get("legal_name")
        if business_name:
            printer.set(align="center", bold=True, width=2, height=2)
            for line in _split_long_line(business_name):
                printer.text(f"{line}\n")
            printer.set(align="center", bold=False, width=1, height=1)
        if business.get("address"):
            for line in _split_long_line(business["address"]):
                printer.text(f"{line}\n")
        if business.get("phone"):
            printer.text(f"Tel: {business['phone'][:32]}\n")
        if business.get("gstin"):
            printer.text(f"GSTIN: {business['gstin'][:32]}\n")
        printer.text("-" * 32 + "\n")

    printer.set(align="center", bold=True, width=2, height=2)
    printer.text("TAX INVOICE\n")
    printer.set(align="center", bold=False, width=1, height=1)
    printer.text(f"{invoice['invoice_number']}\n")
    printer.text(f"{invoice['invoice_date']}\n")
    printer.text("-" * 32 + "\n")

    printer.set(align="left")
    for item in invoice["items"]:
        printer.text(f"{item['product_name'][:32]}\n")
        _line(printer, f"  {item['quantity']} x Rs.{item['unit_price']:.2f}", item["line_total"])

    printer.text("-" * 32 + "\n")
    _line(printer, "Taxable value", invoice["taxable_total"])
    if invoice.get("vat_total"):
        _line(printer, "VAT (15%)", invoice["vat_total"])
    if invoice.get("coupon_discount_amount"):
        _line(printer, f"Coupon ({invoice.get('coupon_code', '')})", -invoice["coupon_discount_amount"])
    _line(printer, "Round off", invoice["round_off"])
    printer.text("-" * 32 + "\n")

    printer.set(bold=True)
    _line(printer, "GRAND TOTAL", invoice["grand_total"])
    printer.set(bold=False)
    printer.text("-" * 32 + "\n")

    for payment in invoice["payments"]:
        _line(printer, payment["method"].upper(), payment["amount"])

    printer.set(align="center")
    footer_note = invoice.get("footer_note")
    printer.text("\n")
    if footer_note:
        for line in _split_long_line(footer_note):
            printer.text(f"{line}\n")
    if not footer_note or invoice.get("thanks_message", True):
        printer.text("Thank you for shopping with us!\n\n")
    else:
        printer.text("\n")
    printer.cut()


def _split_long_line(text: str, width: int = 32) -> list[str]:
    """Wraps a line to the receipt width without breaking words mid-way."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= width:
            current = f"{current} {word}".strip() if current else word
            continue
        if current:
            lines.append(current)
        current = word
    if current:
        lines.append(current)
    if not lines:
        return [""]
    return lines


def _line(printer: EscposPrinter, label: str, amount: float) -> None:
    amount_str = f"SAR.{amount:.2f}"
    padding = max(1, 32 - len(label) - len(amount_str))
    printer.text(f"{label}{' ' * padding}{amount_str}\n")
