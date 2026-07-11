import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import ConflictError, DomainError, InsufficientStockError, NotFoundError, ValidationError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.audit.service import write_audit_log
from app.modules.inventory.schemas import (
    StockAdjustmentRequest,
    StockItemResponse,
    StockTransferCreateRequest,
    StockTransferResponse,
)
from app.modules.inventory.service import InventoryService, StockTransferService

router = APIRouter(prefix="/api/v1/inventory", tags=["inventory"])

_TRANSFER_ERROR_STATUS = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ConflictError: status.HTTP_409_CONFLICT,
    InsufficientStockError: status.HTTP_409_CONFLICT,
}


def _raise_for(exc: DomainError):
    for exc_type, code in _TRANSFER_ERROR_STATUS.items():
        if isinstance(exc, exc_type):
            raise HTTPException(code, str(exc)) from exc
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


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


@router.get("/transfers", response_model=list[StockTransferResponse])
def list_transfers(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.INVENTORY_VIEW))):
    return StockTransferService(db).list_transfers(user.organization_id)


@router.get("/transfers/{transfer_id}", response_model=StockTransferResponse)
def get_transfer(
    transfer_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.INVENTORY_VIEW))
):
    try:
        return StockTransferService(db).get_transfer_or_404(transfer_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.post("/transfers", response_model=StockTransferResponse, status_code=status.HTTP_201_CREATED)
def create_transfer(
    payload: StockTransferCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.INVENTORY_ADJUST)),
):
    service = StockTransferService(db)
    try:
        transfer = service.create_transfer(
            user.organization_id, payload.source_warehouse_id, payload.destination_warehouse_id,
            [i.model_dump() for i in payload.items],
        )
        db.commit()
    except DomainError as exc:
        db.rollback()
        _raise_for(exc)
    return transfer


@router.post("/transfers/{transfer_id}/dispatch", response_model=StockTransferResponse)
def dispatch_transfer(
    transfer_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.INVENTORY_ADJUST)),
):
    service = StockTransferService(db)
    try:
        transfer = service.dispatch_transfer(user.organization_id, transfer_id)
        write_audit_log(db, user.organization_id, user.id, "stock_transfer.dispatch", "stock_transfer", transfer_id)
        db.commit()
    except DomainError as exc:
        db.rollback()
        _raise_for(exc)
    return transfer


@router.post("/transfers/{transfer_id}/receive", response_model=StockTransferResponse)
def receive_transfer(
    transfer_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.INVENTORY_ADJUST)),
):
    service = StockTransferService(db)
    try:
        transfer = service.receive_transfer(user.organization_id, transfer_id)
        write_audit_log(db, user.organization_id, user.id, "stock_transfer.receive", "stock_transfer", transfer_id)
        db.commit()
    except DomainError as exc:
        db.rollback()
        _raise_for(exc)
    return transfer
