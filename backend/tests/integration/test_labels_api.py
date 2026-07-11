def test_barcode_image_endpoint_returns_png(client, seeded_org):
    product_id = seeded_org["product"].id
    resp = client.get(f"/api/v1/catalog/products/{product_id}/barcode.png", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_qr_image_endpoint_returns_png(client, seeded_org):
    product_id = seeded_org["product"].id
    resp = client.get(f"/api/v1/catalog/products/{product_id}/qr.png", headers=seeded_org["auth_headers"])
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


def test_label_sheet_endpoint_returns_png_for_requested_copies(client, seeded_org):
    product_id = seeded_org["product"].id
    resp = client.get(
        f"/api/v1/catalog/products/{product_id}/label-sheet.png",
        headers=seeded_org["auth_headers"],
        params={"copies": 4, "columns": 2},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"


def test_label_endpoints_404_for_unknown_product(client, seeded_org):
    import uuid

    resp = client.get(f"/api/v1/catalog/products/{uuid.uuid4()}/barcode.png", headers=seeded_org["auth_headers"])
    assert resp.status_code == 404


def test_label_sheet_rejects_out_of_range_copies(client, seeded_org):
    product_id = seeded_org["product"].id
    resp = client.get(
        f"/api/v1/catalog/products/{product_id}/label-sheet.png",
        headers=seeded_org["auth_headers"],
        params={"copies": 0},
    )
    assert resp.status_code == 422
