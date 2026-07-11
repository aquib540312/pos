"""Notification channel adapters.

SMS uses MSG91's Flow API (https://docs.msg91.com/p/tf9GTextN/e/pKMhh_bA-A/MSG91),
India's standard transactional SMS provider -- real, documented contract:

    POST https://control.msg91.com/api/v5/flow/
    Headers: authkey: <AUTH_KEY>
    Body: {"template_id": <flow_id>, "recipients": [{"mobiles": "91XXXXXXXXXX", "VAR1": "<message>"}]}

Note: Indian transactional SMS is DLT-regulated (TRAI) -- you cannot send
arbitrary free text, only pre-registered templates with variable slots.
The Flow API call here assumes a template registered on your MSG91
dashboard with a single `{{VAR1}}` placeholder; `flow_id` (POS_MSG91_FLOW_ID)
must point at that template once you have a real account.

WhatsApp and Email remain stubbed (LoggingAdapter) -- see ROADMAP.md for
the WhatsApp Business API / BSP and SMTP provider choices still needed.
Swapping in a real provider for either means implementing
`NotificationAdapter` and adding a branch in `_resolve_adapter`, not
touching any calling code.
"""

import logging
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("app.notifications")


class NotificationAdapter(Protocol):
    def send(self, to: str, message: str) -> None: ...


class LoggingAdapter:
    """Default adapter for any channel with no provider configured."""

    def __init__(self, channel: str):
        self.channel = channel

    def send(self, to: str, message: str) -> None:
        logger.info("[%s] would send to %s: %s", self.channel, to, message)


class MSG91Adapter:
    """Real MSG91 Flow API integration. Network errors are logged, never
    raised -- a notification failure must never break the caller's
    request (e.g. a checkout that also tries to text a receipt)."""

    _BASE_URL = "https://control.msg91.com/api/v5/flow/"

    def __init__(self, auth_key: str, flow_id: str, sender_id: str):
        self.auth_key = auth_key
        self.flow_id = flow_id
        self.sender_id = sender_id

    def send(self, to: str, message: str) -> None:
        mobile = to if to.startswith("91") else f"91{to.lstrip('+').lstrip('0')}"
        try:
            response = httpx.post(
                self._BASE_URL,
                headers={"authkey": self.auth_key, "Content-Type": "application/json"},
                json={
                    "template_id": self.flow_id,
                    "sender": self.sender_id,
                    "recipients": [{"mobiles": mobile, "VAR1": message}],
                },
                timeout=10.0,
            )
            if response.status_code >= 400:
                logger.warning("MSG91 send failed (%s): %s", response.status_code, response.text)
        except httpx.HTTPError as exc:
            logger.warning("MSG91 send failed: %s", exc)


def _resolve_adapter(channel: str, settings: Settings) -> NotificationAdapter:
    if channel == "sms" and settings.msg91_auth_key and settings.msg91_flow_id:
        return MSG91Adapter(settings.msg91_auth_key, settings.msg91_flow_id, settings.msg91_sender_id)
    return LoggingAdapter(channel)


def send_notification(channel: str, to: str, message: str) -> None:
    if channel not in ("sms", "whatsapp", "email"):
        raise ValueError(f"Unknown notification channel: {channel}")
    adapter = _resolve_adapter(channel, get_settings())
    adapter.send(to, message)
