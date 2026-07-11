import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import InsufficientStockError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.audit.service import write_audit_log
from app.modules.inventory.schemas import StockAdjustmentRequest, StockItemResponse
from app.modules.inventory.service import InventoryService

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])


@router.get("/stock", response_model=list[StockItemResponse])
def list_stock(
    warehouse_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.INVENTORY_VIEW)),
):
    return InventoryService(db).list_stock(user.organization_id, warehouse_id)


@router.post("/adjust", response_model=StockItemResponse)
def adjust_stock(
    payload: StockAdjustmentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.INVENTORY_ADJUST)),
):
    service = InventoryService(db)
    try:
        if payload.quantity_delta >= 0:
            item = service.receive(
                user.organization_id, payload.warehouse_id, payload.product_id, payload.batch_id,
                payload.quantity_delta, "adjustment_in", "manual_adjustment", uuid.uuid4(), payload.reason,
            )
        else:
            item = service.issue(
                user.organization_id, payload.warehouse_id, payload.product_id, payload.batch_id,
                -payload.quantity_delta, "adjustment_out", "manual_adjustment", uuid.uuid4(), payload.reason,
            )
        write_audit_log(
            db, user.organization_id, user.id, "inventory.adjust", "product", payload.product_id,
            {"quantity_delta": payload.quantity_delta, "reason": payload.reason},
        )
        db.commit()
    except InsufficientStockError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return item
