"""Captures every create/update/delete of a syncable entity into
`SyncChangeLog`, without any of the entity's own service code having to
remember to do it.

SQLAlchemy's `before_flush` session event fires with the exact set of
objects about to be inserted/updated/deleted in the *current* flush --
adding more objects to the session from inside the handler (our changelog
rows) folds them into that same flush rather than starting a new one, so
this never causes recursion and never misses a write that goes through
`db.flush()`/`db.commit()` from anywhere in the codebase.
"""

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.catalog import Product
from app.models.inventory import StockItem
from app.models.party import Customer
from app.models.sync import SyncChangeLog

# Only the fields a terminal actually needs to rebuild its local read
# cache -- not the full ORM row (e.g. relationships, internal timestamps
# beyond what's listed) -- keeps payloads small and stable.
_TRACKED_FIELDS: dict[type, tuple[str, list[str]]] = {
    Product: (
        "product",
        [
            "id", "organization_id", "sku", "barcode", "name", "description", "category_id", "hsn_code_id",
            "uom_id", "mrp", "sale_price", "purchase_price", "tracks_batches", "tracks_serials", "tracks_expiry",
            "reorder_level", "is_combo", "is_active",
        ],
    ),
    Customer: (
        "customer",
        [
            "id", "organization_id", "name", "phone", "email", "gstin", "state_code", "address",
            "is_credit_customer", "credit_limit", "credit_balance", "loyalty_points_balance", "is_active",
        ],
    ),
    StockItem: ("stock_item", ["id", "organization_id", "warehouse_id", "product_id", "batch_id", "quantity_on_hand"]),
}


def _resolve_pending_default(obj: object, field: str) -> object:
    """Column defaults declared as `default=` (scalar or callable) are
    normally only evaluated by SQLAlchemy while building the INSERT --
    which happens *after* before_flush -- so a freshly-added object's
    Python attributes for those columns still read as None here. Since
    every field this is called on is `nullable=False`, None at this point
    can only mean "default not applied yet," never a legitimate value --
    so it's safe to resolve and assign it ourselves. Doing so also makes
    the INSERT itself use this same value (once an attribute is
    explicitly set, SQLAlchemy won't re-invoke the default), so the
    changelog payload and the actual row can never disagree."""
    value = getattr(obj, field)
    if value is not None:
        return value
    column = obj.__table__.columns[field]
    default = column.default
    if default is None:
        return value
    resolved = default.arg(None) if default.is_callable else default.arg
    setattr(obj, field, resolved)
    return resolved


def _serialize(obj: object, fields: list[str]) -> dict:
    data = {}
    for field in fields:
        value = _resolve_pending_default(obj, field)
        if isinstance(value, uuid.UUID):
            value = str(value)
        data[field] = value
    return data


def _stage_change_log(session: Session, obj: object, operation: str) -> None:
    mapping = _TRACKED_FIELDS.get(type(obj))
    if mapping is None:
        return
    entity_type, fields = mapping

    _resolve_pending_default(obj, "id")

    session.add(
        SyncChangeLog(
            organization_id=obj.organization_id,
            entity_type=entity_type,
            entity_id=obj.id,
            operation=operation,
            payload_json=json.dumps(_serialize(obj, fields), default=str),
            created_at=datetime.now(timezone.utc),
        )
    )


@event.listens_for(Session, "before_flush")
def capture_sync_changes(session: Session, _flush_context: object, _instances: object) -> None:
    for obj in list(session.new):
        _stage_change_log(session, obj, "create")
    for obj in list(session.dirty):
        if type(obj) in _TRACKED_FIELDS and session.is_modified(obj, include_collections=False):
            _stage_change_log(session, obj, "update")
    for obj in list(session.deleted):
        _stage_change_log(session, obj, "delete")
