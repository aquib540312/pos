from __future__ import annotations

import pytest

from sync_agent.config import SyncAgentConfig
from sync_agent.infrastructure.db import LocalDatabase


@pytest.fixture()
def local_db(tmp_path):
    db_path = str(tmp_path / "agent.db")
    db = LocalDatabase(db_path=db_path, encryption_key="", allow_unencrypted=True)
    yield db
    db.close()


@pytest.fixture()
def agent_config():
    return SyncAgentConfig(
        server_base_url="http://testserver",
        terminal_api_key="test-terminal-key",
        db_path=":memory:",
        allow_unencrypted_storage=True,
        sync_interval_seconds=0.05,
        retry_initial_backoff_seconds=0.01,
        retry_max_backoff_seconds=0.05,
        retry_backoff_multiplier=2.0,
        reconnect_check_interval_seconds=0.01,
        push_batch_size=50,
        pull_page_size=500,
    )
