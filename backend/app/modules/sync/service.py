from __future__ import annotations

import json
import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictError,
    CreditLimitExceededError,
    DomainError,
    InsufficientStockError,
    NotFoundError,
    ValidationError,
)
from app.models.sync import OfflineSaleRecord, SyncChangeLog, SyncConflict, SyncTerminal
from app.modules.audit.service import write_audit_log
from app.modules.sales.service import SalesService
from app.modules.sync.repository import (
    OfflineSaleRepository,
    SyncChangeLogRepository,
    SyncConflictRepository,
    SyncTerminalRepository,
)
from app.modules.sync.schemas import OfflineSalePayload, OfflineSaleResult


def _conflict_type_for(exc: DomainError) -> str:
    if isinstance(exc, InsufficientStockError):
        return "insufficient_stock"
    if isinstance(exc, CreditLimitExceededError):
        return "credit_limit_exceeded"
    return "validation_error"


class SyncService:
    """Server side of the bidirectional sync protocol.

    Push and pull are deliberately independent of each other: pushing an
    offline sale never blocks on, or needs, a pull to have happened first,
    and a pull never depends on anything from the current push. Each
    offline sale in a push batch is committed (or rolled back) on its own
    -- not as one all-or-nothing transaction for the whole batch -- so a
    crash or error partway through a large batch leaves the already-applied
    sales applied; the idempotency key on retry skips them and only the
    remainder gets reprocessed.
    """

    def __init__(self, db: Session):
        self.db = db
        self.terminals = SyncTerminalRepository(db)
        self.offline_sales = OfflineSaleRepository(db)
        self.conflicts = SyncConflictRepository(db)
        self.change_log = SyncChangeLogRepository(db)

    # -- Terminal registration -----------------------------------------

    def register_terminal(
        self, organization_id: uuid.UUID, branch_id: uuid.UUID, name: str, device_fingerprint: str
    ) -> SyncTerminal:
        existing = self.terminals.get_by_fingerprint(organization_id, device_fingerprint)
        if existing is not None:
            existing.name = name
            existing.branch_id = branch_id
            existing.is_active = True
            self.db.flush()
            return existing

        terminal = SyncTerminal(
            organization_id=organization_id,
            branch_id=branch_id,
            name=name,
            device_fingerprint=device_fingerprint,
            api_key=secrets.token_hex(24),
        )
        return self.terminals.add(terminal)

    # -- Push: offline sales queue --------------------------------------

    def push_offline_sales(self, terminal: SyncTerminal, sales: list[OfflineSalePayload]) -> list[OfflineSaleResult]:
        results = [self._process_offline_sale(terminal, sale) for sale in sales]
        write_audit_log(
            self.db, terminal.organization_id, None, "sync.push", "sync_terminal", terminal.id,
            {"batch_size": len(sales), "results": [r.status for r in results]},
        )
        self.db.commit()
        return results

    def _process_offline_sale(self, terminal: SyncTerminal, sale: OfflineSalePayload) -> OfflineSaleResult:
        existing = self.offline_sales.get_by_idempotency_key(terminal.id, sale.client_operation_id)
        if existing is not None:
            return self._result_from_record(existing)

        record = OfflineSaleRecord(
            organization_id=terminal.organization_id,
            terminal_id=terminal.id,
            client_operation_id=sale.client_operation_id,
            status="pending",
            payload_json=sale.model_dump_json(),
            occurred_at=sale.occurred_at,
        )
        self.db.add(record)
        try:
            self.db.flush()
        except IntegrityError:
            # Two overlapping pushes raced on the same idempotency key
            # (e.g. a retry fired before the first attempt's response
            # arrived) -- whichever committed first wins; replay its result.
            self.db.rollback()
            existing = self.offline_sales.get_by_idempotency_key(terminal.id, sale.client_operation_id)
            if existing is not None:
                return self._result_from_record(existing)
            raise

        try:
            invoice = SalesService(self.db).create_sale(
                organization_id=terminal.organization_id,
                branch_id=sale.branch_id,
                warehouse_id=sale.warehouse_id,
                customer_id=sale.customer_id,
                shift_id=None,
                items=[item.model_dump() for item in sale.items],
                payments=[payment.model_dump() for payment in sale.payments],
                redeem_loyalty_points=0,
                is_credit_sale=sale.is_credit_sale,
                coupon_code=sale.coupon_code,
            )
        except DomainError as exc:
            self.db.rollback()
            return self._record_conflict(terminal, sale, _conflict_type_for(exc), str(exc))

        record.status = "applied"
        record.invoice_id = invoice.id
        self.db.flush()
        self.db.commit()
        return OfflineSaleResult(client_operation_id=sale.client_operation_id, status="applied", invoice_id=invoice.id)

    def _record_conflict(
        self, terminal: SyncTerminal, sale: OfflineSalePayload, conflict_type: str, message: str
    ) -> OfflineSaleResult:
        """Runs in a fresh transaction after the failed sale attempt was
        rolled back -- the offline sale record itself has to be
        re-inserted here since the rollback above undid the first insert
        too."""
        record = OfflineSaleRecord(
            organization_id=terminal.organization_id,
            terminal_id=terminal.id,
            client_operation_id=sale.client_operation_id,
            status="conflict",
            payload_json=sale.model_dump_json(),
            occurred_at=sale.occurred_at,
            error_detail=message[:1000],
        )
        self.db.add(record)
        self.db.flush()

        conflict = SyncConflict(
            organization_id=terminal.organization_id,
            terminal_id=terminal.id,
            offline_sale_id=record.id,
            conflict_type=conflict_type,
            details_json=json.dumps({"message": message, "sale": json.loads(sale.model_dump_json())}),
        )
        self.db.add(conflict)
        self.db.flush()
        self.db.commit()
        return OfflineSaleResult(
            client_operation_id=sale.client_operation_id,
            status="conflict",
            conflict_id=conflict.id,
            conflict_type=conflict_type,
            error_detail=message,
        )

    # -- Pull: change-log ------------------------------------------------

    def pull(
        self, organization_id: uuid.UUID, cursor: int, entity_types: list[str] | None, limit: int
    ) -> tuple[list[SyncChangeLog], int, bool]:
        return self.change_log.pull(organization_id, cursor, entity_types, limit)

    # -- Conflicts ---------------------------------------------------------

    def list_conflicts(self, organization_id: uuid.UUID, status_filter: str | None = None) -> list[SyncConflict]:
        return self.conflicts.list(organization_id, status_filter)

    def resolve_conflict(
        self,
        organization_id: uuid.UUID,
        conflict_id: uuid.UUID,
        resolution: str,
        notes: str | None,
        user_id: uuid.UUID,
    ) -> SyncConflict:
        conflict = self.conflicts.get(conflict_id)
        if conflict is None or conflict.organization_id != organization_id:
            raise NotFoundError(f"Sync conflict {conflict_id} not found")
        if conflict.status != "open":
            raise ConflictError(f"Sync conflict {conflict_id} is already resolved")

        offline_sale = self.offline_sales.get(conflict.offline_sale_id) if conflict.offline_sale_id else None

        if resolution == "retry":
            if offline_sale is None:
                raise ValidationError("No underlying offline sale to retry")
            sale = OfflineSalePayload.model_validate_json(offline_sale.payload_json)
            terminal = self.terminals.get(offline_sale.terminal_id)
            try:
                invoice = SalesService(self.db).create_sale(
                    organization_id=organization_id,
                    branch_id=sale.branch_id,
                    warehouse_id=sale.warehouse_id,
                    customer_id=sale.customer_id,
                    shift_id=None,
                    items=[item.model_dump() for item in sale.items],
                    payments=[payment.model_dump() for payment in sale.payments],
                    redeem_loyalty_points=0,
                    is_credit_sale=sale.is_credit_sale,
                    coupon_code=sale.coupon_code,
                )
            except DomainError as exc:
                self.db.rollback()
                raise ValidationError(f"Retry failed, conflict still unresolved: {exc}") from exc
            offline_sale.status = "applied"
            offline_sale.invoice_id = invoice.id
            offline_sale.error_detail = None
            _ = terminal  # kept for symmetry / future per-terminal notification hook
        elif resolution == "cancel":
            if offline_sale is not None:
                offline_sale.status = "rejected"
        else:  # pragma: no cover - pydantic Literal already restricts this
            raise ValidationError(f"Unknown resolution '{resolution}'")

        conflict.status = "resolved"
        conflict.resolution = resolution
        conflict.resolution_notes = notes
        conflict.resolved_by_user_id = user_id
        conflict.resolved_at = datetime.now(timezone.utc)
        self.db.flush()

        write_audit_log(
            self.db, organization_id, user_id, "sync.conflict_resolved", "sync_conflict", conflict.id,
            {"resolution": resolution, "conflict_type": conflict.conflict_type},
        )
        return conflict

    # -- Status dashboard --------------------------------------------------

    def status(self, organization_id: uuid.UUID) -> tuple[list[SyncTerminal], int, int]:
        terminals = self.terminals.list(organization_id)
        open_conflicts = self.conflicts.count_open(organization_id)
        latest_change_log_id = self.change_log.latest_id(organization_id)
        return terminals, open_conflicts, latest_change_log_id

    def _result_from_record(self, record: OfflineSaleRecord) -> OfflineSaleResult:
        """Rebuilds the response for a retried push of an
        already-processed offline sale (same idempotency key) -- covers
        the case where the client never saw the original response (e.g.
        connection dropped after the server committed) and retries."""
        conflict_id = None
        conflict_type = None
        if record.status == "conflict":
            conflict = self.conflicts.get_by_offline_sale(record.id)
            if conflict:
                conflict_id = conflict.id
                conflict_type = conflict.conflict_type
        return OfflineSaleResult(
            client_operation_id=record.client_operation_id,
            status=record.status,  # type: ignore[arg-type]
            invoice_id=record.invoice_id,
            conflict_id=conflict_id,
            conflict_type=conflict_type,
            error_detail=record.error_detail,
        )
