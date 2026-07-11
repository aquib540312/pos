import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def write_audit_log(
    db: Session,
    organization_id: uuid.UUID,
    user_id: uuid.UUID | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    log = AuditLog(
        organization_id=organization_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=json.dumps(details) if details else None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.flush()
    return log


def list_audit_logs(db: Session, organization_id: uuid.UUID, limit: int = 200) -> list[AuditLog]:
    stmt = (
        select(AuditLog)
        .where(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars())
