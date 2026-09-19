"""ZATCA (Saudi Arabia) e-invoicing helpers.

Generates a QR code in the ZATCA-mandated TLV (Tag-Length-Value) format
containing the five mandatory fields:

  Tag 1 – Seller name
  Tag 2 – VAT registration number
  Tag 3 – Invoice timestamp (ISO 8601)
  Tag 4 – Invoice total (with VAT)
  Tag 5 – VAT amount

The resulting Base64-encoded string can be rendered as a QR image on
the printed invoice or sent to the ZATCA SDK for clearance/reporting.
"""

import base64
import io
from datetime import datetime

import qrcode


def _tlv_encode(tag: int, value: bytes) -> bytes:
    """Encode a single TLV field: 1-byte tag + 1-byte length + value."""
    return bytes([tag, len(value)]) + value


def generate_zatca_qr_data(
    seller_name: str,
    vat_number: str,
    invoice_date: datetime,
    total_with_vat: float,
    vat_amount: float,
) -> str:
    """Return a Base64-encoded TLV payload for the ZATCA QR code.

    The six mandatory fields are encoded per ZATCA's simplified invoice
    specification.  The result is a short ASCII string suitable for
    embedding in a QR image or appending to the invoice XML.
    """
    fields = [
        _tlv_encode(1, seller_name.encode("utf-8")),
        _tlv_encode(2, vat_number.encode("utf-8")),
        _tlv_encode(3, invoice_date.strftime("%Y-%m-%dT%H:%M:%SZ").encode("utf-8")),
        _tlv_encode(4, f"{total_with_vat:.2f}".encode("utf-8")),
        _tlv_encode(5, f"{vat_amount:.2f}".encode("utf-8")),
    ]
    raw = b"".join(fields)
    return base64.b64encode(raw).decode("ascii")


def generate_zatca_qr_png(qr_data: str) -> bytes:
    """Render the TLV payload as a QR code PNG image."""
    qr = qrcode.QRCode(border=2, box_size=6)
    qr.add_data(qr_data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
