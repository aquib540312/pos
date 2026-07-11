"""Verifies HttpSyncTransport's actual request/response wire format
against the real FastAPI sync API (app.modules.sync) over a genuine
socket -- unlike every other sync_agent test, which uses FakeTransport.

httpx.ASGITransport only implements handle_async_request, so it can't be
plugged into the sync httpx.Client that HttpSyncTransport uses by design
(the background worker does blocking I/O on its own thread, not asyncio)
-- a real server on a loopback port is the correct way to test this."""

from __future__ import annotations

import socket
import threading
import time

import pytest
import uvicorn

from app.main import app as fastapi_app
from sync_agent.domain.transport import AuthenticationError
from sync_agent.infrastructure.http_transport import HttpSyncTransport


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def live_server_base_url(client):
    """`client` (from tests/conftest.py) is requested only for its side
    effect of overriding `get_db` to the test's shared `db_session` --
    the real uvicorn server below serves the same `app` object, so
    requests through it land in the same in-memory database as
    `seeded_org`."""
    port = _free_port()
    config = uvicorn.Config(fastapi_app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 5.0
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.started, "uvicorn server did not start in time"

    yield f"http://127.0.0.1:{port}"

    server.should_exit = True
    thread.join(timeout=5.0)


def test_register_then_push_then_pull_round_trip(live_server_base_url, seeded_org):
    admin_token = seeded_org["auth_headers"]["Authorization"].split(" ", 1)[1]
    transport = HttpSyncTransport(base_url=live_server_base_url, terminal_api_key="")

    registration = transport.register(
        branch_id=str(seeded_org["branch"].id), name="Integration Till", device_fingerprint="itest-device-1",
        auth_token=admin_token,
    )
    assert registration["name"] == "Integration Till"
    assert registration["api_key"]
    transport.close()

    authed_transport = HttpSyncTransport(base_url=live_server_base_url, terminal_api_key=registration["api_key"])
    try:
        push_results = authed_transport.push(
            [
                {
                    "client_operation_id": "op-http-1",
                    "occurred_at": "2026-01-01T00:00:00+00:00",
                    "branch_id": str(seeded_org["branch"].id),
                    "warehouse_id": str(seeded_org["warehouse"].id),
                    "customer_id": None,
                    "items": [{"product_id": str(seeded_org["product"].id), "quantity": 1000}],
                    "payments": [],
                    "is_credit_sale": False,
                    "coupon_code": None,
                }
            ]
        )
        assert len(push_results) == 1
        # No stock was ever received, so this necessarily oversells -- proving
        # the whole client -> server -> conflict path works end to end over
        # a real socket, not just against the FakeTransport.
        assert push_results[0]["status"] == "conflict"
        assert push_results[0]["conflict_type"] == "insufficient_stock"

        pull_page = authed_transport.pull(cursor=0, entity_types=["product"], page_size=10)
        assert isinstance(pull_page["changes"], list)
        assert pull_page["next_cursor"] >= 0

        assert authed_transport.ping() is True
    finally:
        authed_transport.close()


def test_push_with_unknown_api_key_raises_authentication_error(live_server_base_url, seeded_org):
    transport = HttpSyncTransport(base_url=live_server_base_url, terminal_api_key="not-a-real-key")
    try:
        with pytest.raises(AuthenticationError):
            transport.push([])
    finally:
        transport.close()
