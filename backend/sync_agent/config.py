from __future__ import annotations

import os
from dataclasses import dataclass


def _get(env: dict[str, str], prefix: str, name: str, default, cast=str):
    raw = env.get(prefix + name)
    if raw is None:
        return default
    if cast is bool:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    return cast(raw)


@dataclass(frozen=True)
class SyncAgentConfig:
    """Every tunable of the sync engine in one place, all overridable via
    `SYNC_AGENT_*` environment variables (see `from_env`) so an operator
    never has to edit code to change how a terminal syncs."""

    # -- Transport --------------------------------------------------------
    server_base_url: str = "http://localhost:8000"
    terminal_api_key: str = ""
    request_timeout_seconds: float = 15.0

    # -- Local storage ------------------------------------------------------
    db_path: str = "./sync_agent.db"
    db_encryption_key: str = ""
    allow_unencrypted_storage: bool = False  # explicit opt-in escape hatch for local dev/tests only

    # -- Sync cadence & retry -----------------------------------------------
    sync_interval_seconds: float = 30.0
    retry_initial_backoff_seconds: float = 2.0
    retry_max_backoff_seconds: float = 300.0
    retry_backoff_multiplier: float = 2.0
    reconnect_check_interval_seconds: float = 5.0

    # -- Batching / scope -----------------------------------------------------
    push_batch_size: int = 50
    pull_page_size: int = 500
    enabled_entity_types: tuple[str, ...] = ("product", "customer", "stock_item")

    # -- Registration (used only by the one-time `register` command) --------
    branch_id: str = ""
    terminal_name: str = ""
    device_fingerprint: str = ""

    @classmethod
    def from_env(cls, prefix: str = "SYNC_AGENT_", env: dict[str, str] | None = None) -> SyncAgentConfig:
        env = env if env is not None else os.environ
        defaults = cls()
        entity_types_raw = _get(env, prefix, "ENABLED_ENTITY_TYPES", ",".join(defaults.enabled_entity_types))
        return cls(
            server_base_url=_get(env, prefix, "SERVER_BASE_URL", defaults.server_base_url),
            terminal_api_key=_get(env, prefix, "TERMINAL_API_KEY", defaults.terminal_api_key),
            request_timeout_seconds=_get(
                env, prefix, "REQUEST_TIMEOUT_SECONDS", defaults.request_timeout_seconds, float
            ),
            db_path=_get(env, prefix, "DB_PATH", defaults.db_path),
            db_encryption_key=_get(env, prefix, "DB_ENCRYPTION_KEY", defaults.db_encryption_key),
            allow_unencrypted_storage=_get(
                env, prefix, "ALLOW_UNENCRYPTED_STORAGE", defaults.allow_unencrypted_storage, bool
            ),
            sync_interval_seconds=_get(env, prefix, "SYNC_INTERVAL_SECONDS", defaults.sync_interval_seconds, float),
            retry_initial_backoff_seconds=_get(
                env, prefix, "RETRY_INITIAL_BACKOFF_SECONDS", defaults.retry_initial_backoff_seconds, float
            ),
            retry_max_backoff_seconds=_get(
                env, prefix, "RETRY_MAX_BACKOFF_SECONDS", defaults.retry_max_backoff_seconds, float
            ),
            retry_backoff_multiplier=_get(
                env, prefix, "RETRY_BACKOFF_MULTIPLIER", defaults.retry_backoff_multiplier, float
            ),
            reconnect_check_interval_seconds=_get(
                env, prefix, "RECONNECT_CHECK_INTERVAL_SECONDS", defaults.reconnect_check_interval_seconds, float
            ),
            push_batch_size=_get(env, prefix, "PUSH_BATCH_SIZE", defaults.push_batch_size, int),
            pull_page_size=_get(env, prefix, "PULL_PAGE_SIZE", defaults.pull_page_size, int),
            enabled_entity_types=tuple(t.strip() for t in entity_types_raw.split(",") if t.strip()),
            branch_id=_get(env, prefix, "BRANCH_ID", defaults.branch_id),
            terminal_name=_get(env, prefix, "TERMINAL_NAME", defaults.terminal_name),
            device_fingerprint=_get(env, prefix, "DEVICE_FINGERPRINT", defaults.device_fingerprint),
        )

    def with_overrides(self, **kwargs) -> SyncAgentConfig:
        """Dataclasses are frozen (config must never mutate under a
        running worker) -- this returns a new config for the rare case
        a caller needs to override just one or two fields, e.g. in tests."""
        from dataclasses import replace

        return replace(self, **kwargs)
