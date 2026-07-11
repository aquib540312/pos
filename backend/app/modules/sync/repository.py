from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.sync import OfflineSaleRecord, SyncChangeLog, SyncConflict, SyncTerminal


class SyncTerminalRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, terminal: SyncTerminal) -> SyncTerminal:
        self.db.add(terminal)
        self.db.flush()
        return terminal

    def get(self, terminal_id: uuid.UUID) -> SyncTerminal | None:
        return self.db.get(SyncTerminal, terminal_id)

    def get_by_fingerprint(self, organization_id: uuid.UUID, device_fingerprint: str) -> SyncTerminal | None:
        stmt = select(SyncTerminal).where(
            SyncTerminal.organization_id == organization_id, SyncTerminal.device_fingerprint == device_fingerprint
        )
        return self.db.execute(stmt).scalars().first()

    def list(self, organization_id: uuid.UUID) -> list[SyncTerminal]:
        stmt = select(SyncTerminal).where(SyncTerminal.organization_id == organization_id).order_by(SyncTerminal.name)
        return list(self.db.execute(stmt).scalars())


class OfflineSaleRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, record: OfflineSaleRecord) -> OfflineSaleRecord:
        self.db.add(record)
        self.db.flush()
        return record

    def get(self, record_id: uuid.UUID) -> OfflineSaleRecord | None:
        return self.db.get(OfflineSaleRecord, record_id)

    def get_by_idempotency_key(self, terminal_id: uuid.UUID, client_operation_id: str) -> OfflineSaleRecord | None:
        stmt = select(OfflineSaleRecord).where(
            OfflineSaleRecord.terminal_id == terminal_id,
            OfflineSaleRecord.client_operation_id == client_operation_id,
        )
        return self.db.execute(stmt).scalars().first()


class SyncConflictRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, conflict: SyncConflict) -> SyncConflict:
        self.db.add(conflict)
        self.db.flush()
        return conflict

    def get(self, conflict_id: uuid.UUID) -> SyncConflict | None:
        return self.db.get(SyncConflict, conflict_id)

    def get_by_offline_sale(self, offline_sale_id: uuid.UUID) -> SyncConflict | None:
        stmt = select(SyncConflict).where(SyncConflict.offline_sale_id == offline_sale_id)
        return self.db.execute(stmt).scalars().first()

    def list(self, organization_id: uuid.UUID, status_filter: str | None = None) -> list[SyncConflict]:
        stmt = select(SyncConflict).where(SyncConflict.organization_id == organization_id)
        if status_filter:
            stmt = stmt.where(SyncConflict.status == status_filter)
        return list(self.db.execute(stmt.order_by(SyncConflict.created_at.desc())).scalars())

    def count_open(self, organization_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(SyncConflict).where(
            SyncConflict.organization_id == organization_id, SyncConflict.status == "open"
        )
        return self.db.execute(stmt).scalar_one()


class SyncChangeLogRepository:
    def __init__(self, db: Session):
        self.db = db

    def pull(
        self, organization_id: uuid.UUID, cursor: int, entity_types: list[str] | None, limit: int
    ) -> tuple[list[SyncChangeLog], int, bool]:
        stmt = select(SyncChangeLog).where(
            SyncChangeLog.organization_id == organization_id, SyncChangeLog.id > cursor
        )
        if entity_types:
            stmt = stmt.where(SyncChangeLog.entity_type.in_(entity_types))
        stmt = stmt.order_by(SyncChangeLog.id.asc()).limit(limit + 1)
        rows = list(self.db.execute(stmt).scalars())
        has_more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = rows[-1].id if rows else cursor
        return rows, next_cursor, has_more

    def latest_id(self, organization_id: uuid.UUID) -> int:
        stmt = select(func.max(SyncChangeLog.id)).where(SyncChangeLog.organization_id == organization_id)
        return self.db.execute(stmt).scalar_one() or 0
