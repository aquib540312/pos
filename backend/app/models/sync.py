import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import GUID, PortableBigInteger, TimestampMixin, UUIDPKMixin, org_fk


class SyncTerminal(Base, UUIDPKMixin, TimestampMixin):
    """A registered offline-capable POS device (the client running
    `sync_agent`). `api_key` is the bearer credential the terminal presents
    on every push/pull call; `device_fingerprint` makes registration
    idempotent -- re-running setup on the same machine returns the same
    terminal instead of creating a duplicate."""

    __tablename__ = "sync_terminals"
    __table_args__ = (UniqueConstraint("organization_id", "device_fingerprint", name="uq_sync_terminal_fingerprint"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    branch_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("branches.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    device_fingerprint: Mapped[str] = mapped_column(String(200), nullable=False)
    api_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SyncChangeLog(Base):
    """One row per create/update/delete of a syncable entity
    (product/customer/stock_item), in strict insertion order. `id` doubles
    as the cursor a terminal's pull request advances through -- "give me
    everything with id > my_last_cursor" -- so no separate per-org sequence
    is needed: a single global auto-increment column is monotonic enough,
    since each terminal only ever compares against its own previously-seen
    max id. Rows are written by a Session-level `before_flush` listener
    (see `listeners.py`), not by service code, so no existing module has to
    remember to emit one."""

    __tablename__ = "sync_change_log"

    id: Mapped[int] = mapped_column(PortableBigInteger, primary_key=True, autoincrement=True)
    organization_id: Mapped[uuid.UUID] = org_fk()
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    operation: Mapped[str] = mapped_column(String(10), nullable=False)  # create|update|delete
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class OfflineSaleRecord(Base, UUIDPKMixin, TimestampMixin):
    """A sale rung up while a terminal was offline, pushed later. The
    (terminal_id, client_operation_id) unique constraint is what makes
    pushing idempotent: if the same batch is retried after a dropped
    response, the second attempt finds the existing row and returns its
    already-decided outcome instead of creating a second invoice.

    status:
      pending  -- received, not yet processed (transient; normally you
                  never observe this since push processes synchronously)
      applied  -- posted as a real SalesInvoice (`invoice_id` set)
      conflict -- could not be applied safely (e.g. insufficient stock --
                  the oversell policy is "never go negative", so this sale
                  is parked in `SyncConflict` for a human to resolve
                  instead of either silently dropping it or overselling)
      rejected -- permanently invalid (e.g. malformed payload); does not
                  need human resolution, just a record of what happened
    """

    __tablename__ = "offline_sale_records"
    __table_args__ = (
        UniqueConstraint("terminal_id", "client_operation_id", name="uq_offline_sale_idempotency"),
    )

    organization_id: Mapped[uuid.UUID] = org_fk()
    terminal_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("sync_terminals.id"), nullable=False, index=True)
    client_operation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    invoice_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("sales_invoices.id"), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SyncConflict(Base, UUIDPKMixin, TimestampMixin):
    """An offline sale that could not be safely auto-applied. Left `open`
    until a manager resolves it via the sync dashboard -- resolution is a
    business decision (cancel the line, substitute a batch, refund the
    customer), not something the sync engine can decide by itself."""

    __tablename__ = "sync_conflicts"

    organization_id: Mapped[uuid.UUID] = org_fk()
    terminal_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("sync_terminals.id"), nullable=False, index=True)
    offline_sale_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("offline_sale_records.id"), nullable=True
    )
    conflict_type: Mapped[str] = mapped_column(String(30), nullable=False)  # insufficient_stock|validation_error|...
    details_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")  # open|resolved
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)  # cancel|override|substitute
    resolution_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
