from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.sync import SyncTerminal


def get_current_terminal(
    x_terminal_api_key: str = Header(alias="X-Terminal-Api-Key"),
    db: Session = Depends(get_db),
) -> SyncTerminal:
    """Terminals authenticate with a long-lived API key issued at
    registration, not a user JWT -- the background sync worker runs
    unattended, independent of which cashier happens to be logged into the
    till at the moment it syncs."""
    terminal = db.execute(select(SyncTerminal).where(SyncTerminal.api_key == x_terminal_api_key)).scalar_one_or_none()
    if terminal is None or not terminal.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or inactive terminal API key")
    terminal.last_seen_at = datetime.now(timezone.utc)
    # Committed immediately, not just flushed: push's per-sale processing
    # may call db.rollback() later (a conflict rolling back its own failed
    # attempt) -- that must never also erase this liveness timestamp,
    # which has nothing to do with any individual sale's outcome.
    db.commit()
    return terminal
