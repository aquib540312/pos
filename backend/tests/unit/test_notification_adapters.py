import logging

import pytest

from app.modules.notifications.adapters import send_notification


def test_logging_adapter_logs_the_message(caplog):
    with caplog.at_level(logging.INFO, logger="app.notifications"):
        send_notification("sms", "+919999999999", "Your order is ready")
    assert "would send" in caplog.text
    assert "+919999999999" in caplog.text


def test_unknown_channel_raises():
    with pytest.raises(ValueError):
        send_notification("carrier_pigeon", "loft-1", "hi")
