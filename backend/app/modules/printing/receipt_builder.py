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
    if invoice["cgst_total"]:
        _line(printer, "CGST", invoice["cgst_total"])
    if invoice["sgst_total"]:
        _line(printer, "SGST", invoice["sgst_total"])
    if invoice["igst_total"]:
        _line(printer, "IGST", invoice["igst_total"])
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
    printer.text("\nThank you for shopping with us!\n\n")
    printer.cut()


def _line(printer: EscposPrinter, label: str, amount: float) -> None:
    amount_str = f"Rs.{amount:.2f}"
    padding = max(1, 32 - len(label) - len(amount_str))
    printer.text(f"{label}{' ' * padding}{amount_str}\n")
