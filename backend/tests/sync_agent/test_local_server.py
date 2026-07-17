from __future__ import annotations

import json

import httpx
import pytest

from sync_agent.app import build_app
from sync_agent.domain.entities import LocalCustomer, LocalProduct
from sync_agent.local_server import LocalServer


@pytest.fixture()
def sync_app(agent_config):
    app = build_app(agent_config)
    yield app
    app.close()


def _seed_product(app, **overrides):
    defaults = dict(
        id="p1", sku="SKU1", barcode="12345", name="Widget", description=None, category_id=None,
        hsn_code_id=None, uom_id=None, mrp=120.0, sale_price=100.0, purchase_price=70.0,
        tracks_batches=False, tracks_serials=False, tracks_expiry=False, reorder_level=5.0,
        is_combo=False, is_active=True,
    )
    defaults.update(overrides)
    app.products.upsert(LocalProduct(**defaults))


def _seed_customer(app, **overrides):
    defaults = dict(
        id="c1", name="Walk-in Regular", phone="9999999999", email=None, gstin=None, state_code="27",
        address=None, is_credit_customer=False, credit_limit=0.0, credit_balance=0.0,
        loyalty_points_balance=0.0, is_active=True,
    )
    defaults.update(overrides)
    app.customers.upsert(LocalCustomer(**defaults))


def _offline_server(sync_app) -> LocalServer:
    # agent_config's server_base_url ("http://testserver") never resolves,
    # so every request to it raises httpx.ConnectError -- exercising the
    # fallback path without needing a real socket.
    return LocalServer(sync_app)


def test_product_search_falls_back_to_local_cache_when_offline(sync_app):
    _seed_product(sync_app, name="Basmati Rice 5kg")
    server = _offline_server(sync_app)

    status, _, body = server.handle("GET", "/api/v1/catalog/products", {"search": ["rice"]}, {}, b"")

    assert status == 200
    results = json.loads(body)
    assert len(results) == 1
    assert results[0]["name"] == "Basmati Rice 5kg"
    assert results[0]["tax_rate_percent"] is None  # not cached locally, never guessed


def test_product_barcode_lookup_offline(sync_app):
    _seed_product(sync_app, barcode="8901030895565")
    server = _offline_server(sync_app)

    found_status, _, found_body = server.handle(
        "GET", "/api/v1/catalog/products/barcode/8901030895565", {}, {}, b""
    )
    assert found_status == 200
    assert json.loads(found_body)["barcode"] == "8901030895565"

    missing_status, _, missing_body = server.handle(
        "GET", "/api/v1/catalog/products/barcode/0000000000000", {}, {}, b""
    )
    assert missing_status == 404
    assert "detail" in json.loads(missing_body)


def test_customer_search_offline(sync_app):
    _seed_customer(sync_app, name="Registered Buyer Pvt Ltd", phone="8888888888")
    server = _offline_server(sync_app)

    status, _, body = server.handle("GET", "/api/v1/party/customers", {"search": ["registered"]}, {}, b"")

    assert status == 200
    assert json.loads(body)[0]["phone"] == "8888888888"


def test_sale_enqueues_offline_and_returns_provisional_invoice(sync_app):
    _seed_product(sync_app, id="p1", sale_price=100.0)
    server = _offline_server(sync_app)

    request_body = json.dumps(
        {
            "branch_id": "b1",
            "warehouse_id": "w1",
            "customer_id": None,
            "items": [{"product_id": "p1", "quantity": 2, "discount_amount": 0}],
            "payments": [{"method": "cash", "amount": 200}],
        }
    ).encode()

    status, _, body = server.handle("POST", "/api/v1/sales", {}, {}, request_body)

    assert status == 201
    invoice = json.loads(body)
    assert invoice["status"] == "offline_pending"
    assert invoice["invoice_number"].startswith("OFFLINE-")
    assert invoice["grand_total"] == 200.0  # 2 x sale_price(100), no GST claimed offline
    assert invoice["cgst_total"] == 0.0
    assert sync_app.offline_sales.count_pending() == 1


def test_sale_with_gift_card_is_rejected_offline_not_silently_accepted(sync_app):
    server = _offline_server(sync_app)
    request_body = json.dumps(
        {
            "branch_id": "b1",
            "warehouse_id": "w1",
            "items": [{"product_id": "p1", "quantity": 1}],
            "payments": [],
            "gift_card_number": "GC-1",
            "gift_card_amount": 50,
        }
    ).encode()

    status, _, body = server.handle("POST", "/api/v1/sales", {}, {}, request_body)

    assert status == 503
    assert "gift card" in json.loads(body)["detail"].lower()
    assert sync_app.offline_sales.count_pending() == 0


def test_unmapped_path_returns_503_offline_rather_than_guessing(sync_app):
    server = _offline_server(sync_app)
    status, _, body = server.handle("GET", "/api/v1/reports/gstr1", {}, {}, b"")
    assert status == 503
    assert "detail" in json.loads(body)


def test_reachable_upstream_is_proxied_unchanged(sync_app):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/v1/org/branches"
        return httpx.Response(200, json=[{"id": "branch-1", "name": "Main Store"}])

    fake_upstream = httpx.Client(base_url="http://testserver", transport=httpx.MockTransport(handler))
    server = LocalServer(sync_app, upstream=fake_upstream)

    status, _, body = server.handle("GET", "/api/v1/org/branches", {}, {"Authorization": "Bearer test"}, b"")

    assert status == 200
    assert json.loads(body) == [{"id": "branch-1", "name": "Main Store"}]
    fake_upstream.close()
