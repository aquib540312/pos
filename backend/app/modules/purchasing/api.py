import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.purchasing.schemas import (
    GoodsReceiptCreateRequest,
    GoodsReceiptResponse,
    PurchaseOrderCreateRequest,
    PurchaseOrderResponse,
)
from app.modules.purchasing.service import PurchasingService

router = APIRouter(prefix="/api/v1/purchasing", tags=["purchasing"])


@router.get("/purchase-orders", response_model=list[PurchaseOrderResponse])
def list_purchase_orders(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.PURCHASE_CREATE))):
    return PurchasingService(db).purchase_orders.list(user.organization_id)


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
    return PurchasingService(db).goods_receipts.get(grn_id)
