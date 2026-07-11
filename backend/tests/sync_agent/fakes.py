from __future__ import annotations

from sync_agent.domain.transport import AuthenticationError, TransportError


class FakeTransport:
    """An in-memory stand-in for the real server, used by every sync_agent
    test so none of them need a running FastAPI process. Mimics just
    enough of the real /sync/push and /sync/pull semantics (idempotency,
    cursor-based pagination, oversell-safe conflict recording) to exercise
    the client logic honestly."""

    def __init__(self):
        self.registered = None
        self.pushed_batches: list[list[dict]] = []
        self.push_results_by_op_id: dict[str, dict] = {}
        self.change_log: list[dict] = []  # each: {"id": int, "entity_type": ..., "operation": ..., "payload": {...}}
        self.pull_page_size_override: int | None = None
        self.fail_next_push = False
        self.fail_next_pull = False
        self.raise_auth_error = False
        self.ping_result = True
        self.ping_calls = 0

    # -- test setup helpers --------------------------------------------------

    def seed_change(self, entity_type: str, operation: str, entity_id: str, payload: dict) -> None:
        next_id = (self.change_log[-1]["id"] + 1) if self.change_log else 1
        self.change_log.append(
            {"id": next_id, "entity_type": entity_type, "entity_id": entity_id, "operation": operation,
             "payload": payload, "created_at": "2026-01-01T00:00:00+00:00"}
        )

    def set_result_for(self, client_operation_id: str, result: dict) -> None:
        self.push_results_by_op_id[client_operation_id] = result

    # -- SyncTransport protocol -----------------------------------------------

    def register(self, branch_id: str, name: str, device_fingerprint: str, auth_token: str) -> dict:
        self.registered = {"branch_id": branch_id, "name": name, "device_fingerprint": device_fingerprint}
        return {"id": "terminal-1", "name": name, "branch_id": branch_id, "api_key": "issued-api-key"}

    def push(self, offline_sales: list[dict]) -> list[dict]:
        if self.raise_auth_error:
            raise AuthenticationError("invalid api key")
        if self.fail_next_push:
            self.fail_next_push = False
            raise TransportError("connection refused")
        self.pushed_batches.append(offline_sales)
        results = []
        for sale in offline_sales:
            op_id = sale["client_operation_id"]
            if op_id in self.push_results_by_op_id:
                results.append(self.push_results_by_op_id[op_id])
            else:
                default = {"client_operation_id": op_id, "status": "applied", "invoice_id": f"inv-{op_id}"}
                results.append(default)
        return results

    def pull(self, cursor: int, entity_types: list[str] | None, page_size: int) -> dict:
        if self.raise_auth_error:
            raise AuthenticationError("invalid api key")
        if self.fail_next_pull:
            self.fail_next_pull = False
            raise TransportError("connection refused")

        effective_page_size = self.pull_page_size_override or page_size
        candidates = [c for c in self.change_log if c["id"] > cursor]
        if entity_types:
            candidates = [c for c in candidates if c["entity_type"] in entity_types]
        candidates.sort(key=lambda c: c["id"])
        page = candidates[:effective_page_size]
        has_more = len(candidates) > effective_page_size
        next_cursor = page[-1]["id"] if page else cursor
        return {"changes": page, "next_cursor": next_cursor, "has_more": has_more}

    def ping(self) -> bool:
        self.ping_calls += 1
        return self.ping_result

    def close(self) -> None:
        pass
