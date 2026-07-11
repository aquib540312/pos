"""Pure image-generation helpers for barcode/QR product labels.

No DB, no FastAPI -- takes primitives (a code string, a product name/price)
and returns PNG bytes, so it's trivially unit-testable and reusable from
both the label-sheet endpoint and (later) any bulk/offline label-printing
tool without dragging in the web framework.
"""

import io

import barcode
import qrcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont


class InvalidLabelDataError(ValueError):
    """Raised when the given code can't be encoded (e.g. non-ASCII barcode
    value) -- callers translate this to a 422, not a 500."""


def generate_barcode_png(code: str) -> bytes:
    """Code128 is used because it encodes the full ASCII range (unlike
    EAN-13, which requires a 12/13-digit numeric code) -- SKUs in this
    system are free-form alphanumeric strings, not GTINs."""
    try:
        barcode_class = barcode.get_barcode_class("code128")
        instance = barcode_class(code, writer=ImageWriter())
    except barcode.errors.BarcodeError as exc:
        raise InvalidLabelDataError(f"Cannot encode '{code}' as a Code128 barcode: {exc}") from exc

    buffer = io.BytesIO()
    instance.write(buffer, options={"write_text": False, "quiet_zone": 2})
    return buffer.getvalue()


def generate_qr_png(data: str) -> bytes:
    qr = qrcode.QRCode(border=2, box_size=8)
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default()


def generate_label_sheet_png(
    code: str,
    product_name: str,
    price: float,
    copies: int,
    columns: int = 3,
) -> bytes:
    """A printable grid of `copies` identical shelf labels (barcode + name
    + MRP), `columns` per row -- sized for a standard A4/letter sheet of
    self-adhesive label stock on any regular printer, so a shop doesn't
    need dedicated thermal label-printer hardware to get usable barcode
    labels (that remains a Phase 3 item for direct thermal printers --
    see ROADMAP.md)."""
    if copies < 1:
        raise ValueError("copies must be at least 1")

    barcode_png = generate_barcode_png(code)
    barcode_img = Image.open(io.BytesIO(barcode_png)).convert("L")

    label_width, label_height = 300, 160
    barcode_img = barcode_img.resize(
        (label_width - 20, 70), Image.Resampling.LANCZOS
    )

    def render_one_label() -> Image.Image:
        label = Image.new("L", (label_width, label_height), color=255)
        draw = ImageDraw.Draw(label)
        name_font = _load_font(16)
        price_font = _load_font(18)

        draw.text((10, 8), product_name[:28], fill=0, font=name_font)
        label.paste(barcode_img, (10, 32))
        draw.text((10, 108), code, fill=0, font=name_font)
        draw.text((10, 128), f"MRP: Rs.{price:.2f}", fill=0, font=price_font)
        return label

    rows = (copies + columns - 1) // columns
    sheet = Image.new("L", (label_width * columns, label_height * rows), color=255)
    for i in range(copies):
        row, col = divmod(i, columns)
        sheet.paste(render_one_label(), (col * label_width, row * label_height))

    buffer = io.BytesIO()
    sheet.save(buffer, format="PNG")
    return buffer.getvalue()
