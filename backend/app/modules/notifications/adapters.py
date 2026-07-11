"""Notification channel adapters.

Each channel (SMS, WhatsApp, Email) is a real integration in production but
needs a provider account and API keys we don't have (see ROADMAP.md Phase
3: MSG91/Twilio for SMS, WhatsApp Business API via Meta or a BSP like
Gupshup/Interakt, and any SMTP/SES provider for email). Until those
credentials exist, every adapter here just logs what it *would* send --
swapping in a real provider later means implementing `NotificationAdapter`
and registering it in `ADAPTERS`, not touching any calling code.
"""

import logging
from typing import Protocol

logger = logging.getLogger("app.notifications")


class NotificationAdapter(Protocol):
    def send(self, to: str, message: str) -> None: ...


class LoggingAdapter:
    """Default adapter for every channel until a real provider is configured."""

    def __init__(self, channel: str):
        self.channel = channel

    def send(self, to: str, message: str) -> None:
        logger.info("[%s] would send to %s: %s", self.channel, to, message)


ADAPTERS: dict[str, NotificationAdapter] = {
    "sms": LoggingAdapter("sms"),
    "whatsapp": LoggingAdapter("whatsapp"),
    "email": LoggingAdapter("email"),
}


def send_notification(channel: str, to: str, message: str) -> None:
    adapter = ADAPTERS.get(channel)
    if adapter is None:
        raise ValueError(f"Unknown notification channel: {channel}")
    adapter.send(to, message)
