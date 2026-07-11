"""Dispatches a rendered receipt to the configured printer.

Swapping the placeholder IP for a real Epson TM-series (or any ESC/POS-
compatible) network printer is a config change only: set
POS_PRINTER_HOST/POS_PRINTER_PORT to the printer's LAN IP (ESC/POS
printers listen on raw TCP port 9100 by convention) and POS_PRINTER_ENABLED
to true. Nothing in this module or its callers needs to change.
"""

import logging

from escpos.exceptions import Error as EscposError
from escpos.printer import Dummy, Network

from app.core.config import Settings, get_settings
from app.modules.printing.receipt_builder import render_receipt

logger = logging.getLogger("app.printing")


class PrintService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def render_to_bytes(self, invoice: dict) -> bytes:
        """Returns the raw ESC/POS byte stream for an invoice without
        touching any hardware -- useful for previewing, or for setups
        that pipe raw ESC/POS bytes to a printer via the OS print spooler
        instead of a direct network socket."""
        printer = Dummy()
        render_receipt(printer, invoice)
        return bytes(printer.output)

    def print_invoice(self, invoice: dict) -> bool:
        """Best-effort hardware print. Returns whether it actually sent
        (False on any failure) but never raises -- a jammed/offline/
        misconfigured printer must never be able to break a checkout or
        a background print job."""
        if not self.settings.printer_enabled:
            logger.info("Printing disabled (POS_PRINTER_ENABLED=false); skipping receipt %s", invoice.get("invoice_number"))
            return False
        try:
            printer = Network(self.settings.printer_host, port=self.settings.printer_port, timeout=5)
            try:
                render_receipt(printer, invoice)
            finally:
                printer.close()
            return True
        except (EscposError, OSError) as exc:
            logger.warning("Failed to print receipt %s: %s", invoice.get("invoice_number"), exc)
            return False


def invoice_to_print_payload(invoice, product_names: dict) -> dict:
    """Flattens a SalesInvoice ORM object (with items/payments loaded)
    into the plain dict `render_receipt` expects, decoupling the printer
    formatting code from the ORM. `product_names` maps product_id -> name
    (built by the caller, which already has catalog access) since
    SalesInvoiceItem only stores the product_id FK, not a denormalized
    name."""
    return {
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.strftime("%d-%b-%Y %H:%M"),
        "items": [
            {
                "product_name": product_names.get(item.product_id, str(item.product_id)),
                "quantity": float(item.quantity),
                "unit_price": float(item.unit_price),
                "line_total": float(item.line_total),
            }
            for item in invoice.items
        ],
        "taxable_total": float(invoice.taxable_total),
        "cgst_total": float(invoice.cgst_total),
        "sgst_total": float(invoice.sgst_total),
        "igst_total": float(invoice.igst_total),
        "coupon_code": invoice.coupon_code,
        "coupon_discount_amount": float(invoice.coupon_discount_amount),
        "round_off": float(invoice.round_off),
        "grand_total": float(invoice.grand_total),
        "payments": [{"method": p.method, "amount": float(p.amount)} for p in invoice.payments],
    }
