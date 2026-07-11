from __future__ import annotations

import httpx

from sync_agent.domain.transport import AuthenticationError, TransportError


class HttpSyncTransport:
    """The one concrete `SyncTransport` this project ships -- talks to the
    FastAPI backend's `/api/v1/sync/*` endpoints over plain HTTP(S). Any
    `httpx` failure (connection refused, DNS failure, timeout) is
    translated to `TransportError`; a 401 becomes `AuthenticationError`;
    everything else is also a `TransportError` carrying the status/body,
    since from the sync service's point of view "the server didn't like
    this" and "the network is down" are both just "try again later"
    except for auth, which needs a human."""

    def __init__(self, base_url: str, terminal_api_key: str, timeout_seconds: float = 15.0):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/") + "/api/v1/sync",
            headers={"X-Terminal-Api-Key": terminal_api_key} if terminal_api_key else {},
            timeout=timeout_seconds,
        )

    def register(self, branch_id: str, name: str, device_fingerprint: str, auth_token: str) -> dict:
        try:
            resp = self._client.post(
                "/register",
                json={"branch_id": branch_id, "name": name, "device_fingerprint": device_fingerprint},
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        except httpx.HTTPError as exc:
            raise TransportError(str(exc)) from exc
        self._raise_for_status(resp)
        return resp.json()

    def push(self, offline_sales: list[dict]) -> list[dict]:
        try:
            resp = self._client.post("/push", json={"offline_sales": offline_sales})
        except httpx.HTTPError as exc:
            raise TransportError(str(exc)) from exc
        self._raise_for_status(resp)
        return resp.json()["results"]

    def pull(self, cursor: int, entity_types: list[str] | None, page_size: int) -> dict:
        params: dict[str, str | int] = {"cursor": cursor}
        if entity_types:
            params["entity_types"] = ",".join(entity_types)
        try:
            resp = self._client.get("/pull", params=params)
        except httpx.HTTPError as exc:
            raise TransportError(str(exc)) from exc
        self._raise_for_status(resp)
        return resp.json()

    def ping(self) -> bool:
        try:
            resp = self._client.get("/pull", params={"cursor": 0, "entity_types": "product"})
            return resp.status_code < 500
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        self._client.close()

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        if resp.status_code == 401:
            raise AuthenticationError(resp.text)
        if resp.status_code >= 400:
            raise TransportError(f"HTTP {resp.status_code}: {resp.text}")
