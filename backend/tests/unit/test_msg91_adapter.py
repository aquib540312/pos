from app.core.config import Settings
from app.modules.notifications.adapters import LoggingAdapter, MSG91Adapter, _resolve_adapter


def test_resolve_adapter_falls_back_to_logging_when_unconfigured():
    settings = Settings(msg91_auth_key="", msg91_flow_id="")
    adapter = _resolve_adapter("sms", settings)
    assert isinstance(adapter, LoggingAdapter)


def test_resolve_adapter_picks_msg91_when_configured():
    settings = Settings(msg91_auth_key="fake-key", msg91_flow_id="fake-flow")
    adapter = _resolve_adapter("sms", settings)
    assert isinstance(adapter, MSG91Adapter)


def test_resolve_adapter_whatsapp_and_email_still_stubbed():
    settings = Settings(msg91_auth_key="fake-key", msg91_flow_id="fake-flow")
    assert isinstance(_resolve_adapter("whatsapp", settings), LoggingAdapter)
    assert isinstance(_resolve_adapter("email", settings), LoggingAdapter)


def test_msg91_send_posts_expected_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200
        text = "ok"

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("app.modules.notifications.adapters.httpx.post", fake_post)

    adapter = MSG91Adapter(auth_key="fake-key", flow_id="fake-flow", sender_id="POSAPP")
    adapter.send("9876543210", "Your order is ready")

    assert captured["url"] == "https://control.msg91.com/api/v5/flow/"
    assert captured["headers"]["authkey"] == "fake-key"
    assert captured["json"]["template_id"] == "fake-flow"
    assert captured["json"]["recipients"] == [{"mobiles": "919876543210", "VAR1": "Your order is ready"}]


def test_msg91_send_swallows_network_errors(monkeypatch):
    import httpx

    def fake_post(*args, **kwargs):
        raise httpx.ConnectError("network unreachable")

    monkeypatch.setattr("app.modules.notifications.adapters.httpx.post", fake_post)

    adapter = MSG91Adapter(auth_key="fake-key", flow_id="fake-flow", sender_id="POSAPP")
    adapter.send("9876543210", "hi")  # must not raise
