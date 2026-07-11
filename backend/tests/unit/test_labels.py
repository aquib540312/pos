import io

import pytest
from PIL import Image

from app.modules.catalog.labels import (
    InvalidLabelDataError,
    generate_barcode_png,
    generate_label_sheet_png,
    generate_qr_png,
)


def test_generate_barcode_png_produces_valid_image():
    png = generate_barcode_png("BRD-001")
    image = Image.open(io.BytesIO(png))
    assert image.format == "PNG"
    assert image.width > 0 and image.height > 0


def test_generate_barcode_png_rejects_non_ascii():
    with pytest.raises(InvalidLabelDataError):
        generate_barcode_png("héllo")


def test_generate_qr_png_produces_valid_image():
    png = generate_qr_png("SKU:BRD-001|White Bread|MRP:45.0")
    image = Image.open(io.BytesIO(png))
    assert image.format == "PNG"


def test_label_sheet_lays_out_requested_copies_in_a_grid():
    png = generate_label_sheet_png("8901234567890", "White Bread 400g", 45.0, copies=5, columns=3)
    image = Image.open(io.BytesIO(png))
    # 5 copies at 3 columns -> 2 rows
    assert image.width == 300 * 3
    assert image.height == 160 * 2


def test_label_sheet_rejects_zero_copies():
    with pytest.raises(ValueError):
        generate_label_sheet_png("123", "Product", 10.0, copies=0)
