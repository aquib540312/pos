"""Serves the POS frontend one local HTTP port to talk to, whether the
till is online or not -- the thing ROADMAP.md called "embedding
sync_agent as the desktop shell's local data layer."

Every request is tried against the real backend first (`_proxy`) so
online behavior is byte-identical to the frontend talking to the backend
directly; only a network failure falls through to `_offline_fallback`,
which serves the narrow subset this package actually has a safe local
answer for: product/customer lookup from the synced SQLite cache
(`sync_agent/infrastructure/sqlite_repositories.py`), and sale creation
via the existing offline queue (`services/offline_sales_queue.py`).
Everything else -- auth, reports, gift cards, payment gateway, anything
outside the sync engine's scope -- has no cache to fall back to, so it
returns a plain 503 rather than inventing an answer.

Deliberately stdlib-only (`http.server`), matching this package's
existing "runnable on a bare POS terminal" footprint (see
requirements.txt) -- a full web framework isn't needed for one small
proxy+fallback surface.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import httpx

from sync_agent.app import SyncAgentApp, build_app
from sync_agent.config import SyncAgentConfig
from sync_agent.services.offline_sales_queue import OfflineSalesQueueService, ValidationError

logger = logging.getLogger("sync_agent.local_server")

_PRODUCTS_PATH = re.compile(r"^/api/v1/catalog/products/?$")
_PRODUCT_BARCODE_PATH = re.compile(r"^/api/v1/catalog/products/barcode/(?P<barcode>[^/]+)$")
_CUSTOMERS_PATH = re.compile(r"^/api/v1/party/customers/?$")
_SALES_PATH = re.compile(r"^/api/v1/sales/?$")

_HOP_BY_HOP_REQUEST_HEADERS = {"host", "content-length", "connection"}
_HOP_BY_HOP_RESPONSE_HEADERS = {"content-length", "transfer-encoding", "connection"}


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization",
    }


def _json_response(status: int, payload: dict | list) -> tuple[int, dict[str, str], bytes]:
    body = json.dumps(payload).encode("utf-8")
    return status, {"Content-Type": "application/json"}, body


def _product_to_dict(p) -> dict:
    return {
        "id": p.id,
        "sku": p.sku,
        "barcode": p.barcode,
        "name": p.name,
        "mrp": p.mrp,
        "sale_price": p.sale_price,
        "purchase_price": p.purchase_price,
        # Tax rates aren't a synced entity type (see ARCHITECTURE.md #5's
        # enabled_entity_types) -- an offline sale's GST is reconciled
        # server-side once it syncs, never guessed at here.
        "tax_rate_percent": None,
        "tracks_batches": p.tracks_batches,
        "tracks_serials": p.tracks_serials,
        "tracks_expiry": p.tracks_expiry,
        "is_active": p.is_active,
    }


def _customer_to_dict(c) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "email": c.email,
        "gstin": c.gstin,
        "state_code": c.state_code,
        "is_credit_customer": c.is_credit_customer,
        "credit_limit": c.credit_limit,
        "credit_balance": c.credit_balance,
        "loyalty_points_balance": c.loyalty_points_balance,
    }


class LocalServer:
    def __init__(self, app: SyncAgentApp, upstream: httpx.Client | None = None):
        self.app = app
        self.sales_queue = OfflineSalesQueueService(app.offline_sales, app.audit_log)
        # Injectable so tests can point "upstream" at an in-process fake
        # instead of a real socket (see tests/sync_agent/test_local_server.py).
        self._upstream = upstream or httpx.Client(base_url=app.config.server_base_url, timeout=8.0)

    def close(self) -> None:
        self._upstream.close()

    def handle(
        self, method: str, path: str, query: dict[str, list[str]], headers: dict[str, str], body: bytes
    ) -> tuple[int, dict[str, str], bytes]:
        try:
            return self._proxy(method, path, query, headers, body)
        except httpx.HTTPError as exc:
            logger.info("Upstream unreachable (%s); serving %s %s from local fallback", exc, method, path)
            return self._offline_fallback(method, path, query, headers, body)

    def _proxy(
        self, method: str, path: str, query: dict[str, list[str]], headers: dict[str, str], body: bytes
    ) -> tuple[int, dict[str, str], bytes]:
        forward_headers = {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP_REQUEST_HEADERS}
        resp = self._upstream.request(method, path, params=query, headers=forward_headers, content=body or None)
        resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in _HOP_BY_HOP_RESPONSE_HEADERS}
        return resp.status_code, resp_headers, resp.content

    def _offline_fallback(
        self, method: str, path: str, query: dict[str, list[str]], headers: dict[str, str], body: bytes
    ) -> tuple[int, dict[str, str], bytes]:
        if method == "GET" and _PRODUCTS_PATH.match(path):
            return self._search_products(query.get("search", [""])[0])

        barcode_match = _PRODUCT_BARCODE_PATH.match(path)
        if method == "GET" and barcode_match:
            return self._product_by_barcode(barcode_match.group("barcode"))

        if method == "GET" and _CUSTOMERS_PATH.match(path):
            return self._search_customers(query.get("search", [""])[0])

        if method == "POST" and _SALES_PATH.match(path):
            return self._enqueue_sale(body)

        return _json_response(503, {"detail": "Offline: this action needs a connection to the server."})

    def _search_products(self, search: str) -> tuple[int, dict[str, str], bytes]:
        needle = search.strip().lower()
        results = [
            p
            for p in self.app.products.list_all()
            if not needle or needle in p.name.lower() or needle in p.sku.lower() or (p.barcode and needle in p.barcode.lower())
        ]
        return _json_response(200, [_product_to_dict(p) for p in results[:20]])

    def _product_by_barcode(self, barcode: str) -> tuple[int, dict[str, str], bytes]:
        for p in self.app.products.list_all():
            if p.barcode == barcode:
                return _json_response(200, _product_to_dict(p))
        return _json_response(404, {"detail": f"Product with barcode {barcode!r} not found (offline cache)"})

    def _search_customers(self, search: str) -> tuple[int, dict[str, str], bytes]:
        needle = search.strip().lower()
        results = [
            c
            for c in self.app.customers.list_all()
            if not needle or needle in c.name.lower() or (c.phone and needle in c.phone.lower())
        ]
        return _json_response(200, [_customer_to_dict(c) for c in results[:20]])

    def _enqueue_sale(self, body: bytes) -> tuple[int, dict[str, str], bytes]:
        try:
            payload = json.loads(body or b"{}")
        except json.JSONDecodeError:
            return _json_response(400, {"detail": "Invalid JSON body"})

        if payload.get("payment_gateway_transaction_id") or payload.get("gift_card_number"):
            return _json_response(
                503,
                {
                    "detail": "Offline: UPI QR and gift card payments need a connection. "
                    "Use cash/card, or wait for connectivity."
                },
            )

        try:
            sale = self.sales_queue.enqueue_sale(
                branch_id=str(payload.get("branch_id") or ""),
                warehouse_id=str(payload.get("warehouse_id") or ""),
                items=payload.get("items") or [],
                payments=payload.get("payments") or [],
                customer_id=payload.get("customer_id"),
                is_credit_sale=bool(payload.get("is_credit_sale", False)),
                coupon_code=payload.get("coupon_code"),
            )
        except ValidationError as exc:
            return _json_response(422, {"detail": str(exc)})

        return _json_response(201, self._provisional_invoice(sale))

    def _provisional_invoice(self, sale) -> dict:
        """Best-effort receipt data for a sale that only exists in the
        local queue so far -- not a tax invoice (no GSTIN-backed GST
        split is possible without cached tax rates), which is why
        `status` is "offline_pending" rather than "posted": the frontend
        uses that to print a provisional slip instead of claiming this is
        the final GST document. The real tax invoice is created server-
        side, with real tax rates, once this sale syncs."""
        items = []
        subtotal = 0.0
        for line in sale.items:
            product = self.app.products.get(line.product_id)
            unit_price = line.unit_price if line.unit_price is not None else (product.sale_price if product else 0.0)
            line_total = round(unit_price * line.quantity - line.discount_amount, 2)
            subtotal += line_total
            items.append(
                {
                    "id": str(uuid.uuid4()),
                    "product_id": line.product_id,
                    "quantity": line.quantity,
                    "unit_price": unit_price,
                    "discount_amount": line.discount_amount,
                    "taxable_value": line_total,
                    "tax_rate_percent": None,
                    "cgst_amount": 0.0,
                    "sgst_amount": 0.0,
                    "igst_amount": 0.0,
                    "cess_amount": 0.0,
                    "line_total": line_total,
                }
            )
        subtotal = round(subtotal, 2)
        return {
            "id": sale.client_operation_id,
            "invoice_number": f"OFFLINE-{sale.client_operation_id[:8].upper()}",
            "invoice_date": sale.occurred_at,
            "branch_id": sale.branch_id,
            "customer_id": sale.customer_id,
            "is_inter_state": False,
            "subtotal": subtotal,
            "discount_total": 0.0,
            "taxable_total": subtotal,
            "cgst_total": 0.0,
            "sgst_total": 0.0,
            "igst_total": 0.0,
            "cess_total": 0.0,
            "round_off": 0.0,
            "grand_total": subtotal,
            "is_credit_sale": sale.is_credit_sale,
            "status": "offline_pending",
            "loyalty_points_earned": 0.0,
            "loyalty_points_redeemed": 0.0,
            "coupon_code": sale.coupon_code,
            "coupon_discount_amount": 0.0,
            "items": items,
            "payments": [
                {"id": str(uuid.uuid4()), "method": p.method, "amount": p.amount, "reference": p.reference}
                for p in sale.payments
            ],
        }


class _RequestHandler(BaseHTTPRequestHandler):
    server_version = "POSLocalServer/1.0"

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = self.rfile.read(length) if length else b""
        headers = dict(self.headers.items())

        if parsed.path == "/health":
            status, resp_headers, resp_body = _json_response(200, {"status": "ok"})
        else:
            status, resp_headers, resp_body = self.server.local_app.handle(method, parsed.path, query, headers, body)  # type: ignore[attr-defined]

        self.send_response(status)
        for key, value in {**resp_headers, **_cors_headers()}.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(resp_body)))
        self.end_headers()
        self.wfile.write(resp_body)

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_PUT(self) -> None:
        self._dispatch("PUT")

    def do_PATCH(self) -> None:
        self._dispatch("PATCH")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        for key, value in _cors_headers().items():
            self.send_header(key, value)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003 - stdlib override signature
        logger.debug(fmt, *args)


def make_server(app: SyncAgentApp) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((app.config.local_server_host, app.config.local_server_port), _RequestHandler)
    httpd.local_app = LocalServer(app)  # type: ignore[attr-defined]
    return httpd


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    config = SyncAgentConfig.from_env()
    app = build_app(config)
    app.worker.start()
    httpd = make_server(app)
    print(f"sync_agent local server listening on http://{config.local_server_host}:{config.local_server_port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        httpd.local_app.close()  # type: ignore[attr-defined]
        app.worker.stop()
        app.close()


if __name__ == "__main__":
    main()
