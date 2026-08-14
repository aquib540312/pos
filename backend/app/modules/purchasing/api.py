import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import ConflictError, DomainError, InsufficientStockError, NotFoundError, ValidationError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.audit.service import write_audit_log
from app.modules.purchasing.schemas import (
    GoodsReceiptCreateRequest,
    GoodsReceiptResponse,
    PendingGRNItem,
    PurchaseOrderCreateRequest,
    PurchaseOrderResponse,
    PurchaseOrderStatusUpdateRequest,
    PurchaseReturnCreateRequest,
    PurchaseReturnResponse,
)
from app.modules.purchasing.service import PurchasingService

router = APIRouter(prefix="/api/v1/purchasing", tags=["purchasing"])

_RETURN_ERROR_STATUS = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ValidationError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ConflictError: status.HTTP_409_CONFLICT,
    InsufficientStockError: status.HTTP_409_CONFLICT,
}


def _raise_domain(exc: DomainError):
    for exc_type, code in _RETURN_ERROR_STATUS.items():
        if isinstance(exc, exc_type):
            raise HTTPException(code, str(exc)) from exc
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/purchase-orders", response_model=list[PurchaseOrderResponse])
def list_purchase_orders(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.PURCHASE_CREATE))):
    return PurchasingService(db).purchase_orders.list(user.organization_id)


@router.get("/purchase-orders/pending", response_model=list[PendingGRNItem])
def pending_grn(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.PURCHASE_RECEIVE))):
    """Under-delivered POs: lines still owed by the supplier (received <
    ordered), showing the outstanding quantity for each."""
    return PurchasingService(db).pending_grn(user.organization_id)


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderResponse)
def get_purchase_order(
    po_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.PURCHASE_CREATE))
):
    po = PurchasingService(db).purchase_orders.get(po_id)
    if po is None or po.organization_id != user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Purchase order {po_id} not found")
    return po


@router.post("/purchase-orders", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PURCHASE_CREATE)),
):
    po = PurchasingService(db).create_purchase_order(
        organization_id=user.organization_id,
        branch_id=payload.branch_id,
        supplier_id=payload.supplier_id,
        order_date=payload.order_date,
        notes=payload.notes,
        items=[i.model_dump() for i in payload.items],
    )
    db.commit()
    return po


@router.patch("/purchase-orders/{po_id}/status", response_model=PurchaseOrderResponse)
def update_purchase_order_status(
    po_id: uuid.UUID,
    payload: PurchaseOrderStatusUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PURCHASE_CREATE)),
):
    service = PurchasingService(db)
    try:
        po = service.update_po_status(user.organization_id, po_id, payload.status)
        write_audit_log(db, user.organization_id, user.id, "purchase_order.status", "purchase_order", po.id, {"status": payload.status})
        db.commit()
    except DomainError as exc:
        db.rollback()
        raise HTTPException(
            status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_409_CONFLICT,
            str(exc),
        ) from exc
    return po


@router.post("/goods-receipts", response_model=GoodsReceiptResponse, status_code=status.HTTP_201_CREATED)
def create_goods_receipt(
    payload: GoodsReceiptCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PURCHASE_RECEIVE)),
):
    grn = PurchasingService(db).receive_goods(
        organization_id=user.organization_id,
        warehouse_id=payload.warehouse_id,
        supplier_id=payload.supplier_id,
        purchase_order_id=payload.purchase_order_id,
        supplier_invoice_number=payload.supplier_invoice_number,
        items=[i.model_dump() for i in payload.items],
    )
    db.commit()
    return grn


@router.get("/goods-receipts", response_model=list[GoodsReceiptResponse])
def list_goods_receipts(
    db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.PURCHASE_RECEIVE))
):
    return PurchasingService(db).goods_receipts.list(user.organization_id)


@router.get("/goods-receipts/{grn_id}", response_model=GoodsReceiptResponse)
def get_goods_receipt(
    grn_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.PURCHASE_RECEIVE))
):
    grn = PurchasingService(db).goods_receipts.get(grn_id)
    if grn is None or grn.organization_id != user.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Goods receipt {grn_id} not found")
    return grn


@router.post("/purchase-returns", response_model=PurchaseReturnResponse, status_code=status.HTTP_201_CREATED)
def create_purchase_return(
    payload: PurchaseReturnCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PURCHASE_RECEIVE)),
):
    service = PurchasingService(db)
    try:
        from app.models.organization import Warehouse

        warehouse = db.get(Warehouse, payload.warehouse_id)
        if warehouse is None:
            raise NotFoundError(f"Warehouse {payload.warehouse_id} not found")
        purchase_return = service.create_purchase_return(
            organization_id=user.organization_id,
            branch_id=warehouse.branch_id,
            warehouse_id=payload.warehouse_id,
            supplier_id=payload.supplier_id,
            reason=payload.reason,
            items=[i.model_dump() for i in payload.items],
        )
        write_audit_log(
            db, user.organization_id, user.id, "purchase.return", "purchase_return", purchase_return.id,
            {"warehouse_id": str(payload.warehouse_id), "supplier_id": str(payload.supplier_id)},
        )
        db.commit()
    except DomainError as exc:
        db.rollback()
        _raise_domain(exc)
    return purchase_return


@router.get("/purchase-returns", response_model=list[PurchaseReturnResponse])
def list_purchase_returns(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.PURCHASE_RECEIVE))):
    return PurchasingService(db).list_purchase_returns(user.organization_id)


@router.get("/purchase-returns/{purchase_return_id}", response_model=PurchaseReturnResponse)
def get_purchase_return(
    purchase_return_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.PURCHASE_RECEIVE)),
):
    service = PurchasingService(db)
    try:
        return service.get_purchase_return_or_404(user.organization_id, purchase_return_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
