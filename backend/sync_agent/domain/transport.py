from __future__ import annotations

from typing import Protocol


class TransportError(Exception):
    """Raised for any transport-level failure (network unreachable, DNS
    failure, timeout, TLS error, 5xx). Callers (the sync service /
    background worker) catch only this -- never httpx- or any other
    library-specific exception -- which is what keeps the transport
    genuinely swappable: a websocket or gRPC implementation raises the
    same type for the same class of problem."""


class AuthenticationError(Exception):
    """The server rejected the terminal's credentials (401) -- distinct
    from TransportError because retrying with backoff can't fix it; it
    needs an operator to re-register the terminal."""


class SyncTransport(Protocol):
    """Everything the sync engine needs from "the network," kept to
    plain dicts/primitives rather than pydantic/FastAPI types so a
    completely different backend (or wire protocol) could implement this
    same interface without pulling in this project's server code at all."""

    def register(self, branch_id: str, name: str, device_fingerprint: str, auth_token: str) -> dict:
        """One-time bootstrap, authenticated with a manager/admin's user
        JWT (`auth_token`) rather than a terminal API key -- the terminal
        doesn't have one yet, that's what this call produces."""
        ...

    def push(self, offline_sales: list[dict]) -> list[dict]: ...

    def pull(self, cursor: int, entity_types: list[str] | None, page_size: int) -> dict: ...

    def ping(self) -> bool:
        """A cheap reachability probe used for reconnect detection --
        must not raise; return False on any failure."""
        ...
