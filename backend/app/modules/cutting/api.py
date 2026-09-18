import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.cutting.schemas import (
    CuttingOrderCreateRequest,
    CuttingOrderResponse,
    CuttingItemResponse,
)
from app.modules.cutting.service import CuttingService

router = APIRouter(prefix="/api/v1/cutting", tags=["cutting"])


@router.get("/orders", response_model=list[CuttingOrderResponse])
def list_cutting_orders(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.INVENTORY_VIEW)),
):
    orders = CuttingService(db).list_orders(user.organization_id)
    result = []
    for order in orders:
        items = [
            CuttingItemResponse(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product.name if item.product else "",
                output_weight=item.output_weight,
                waste_weight=item.waste_weight,
            )
            for item in order.items
        ]
        result.append(CuttingOrderResponse(
            id=order.id,
            source_product_id=order.source_product_id,
            source_product_name=order.source_product.name if order.source_product else "",
            input_weight=order.input_weight,
            butcher_name=order.butcher_name,
            cutting_date=order.cutting_date,
            status=order.status,
            notes=order.notes,
            items=items,
            created_at=order.created_at,
        ))
    return result


@router.post("/orders", response_model=CuttingOrderResponse, status_code=status.HTTP_201_CREATED)
def create_cutting_order(
    payload: CuttingOrderCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.INVENTORY_ADJUST)),
):
    service = CuttingService(db)
    try:
        order = service.create_order(
            user.organization_id,
            payload.source_product_id,
            payload.input_weight,
            [item.model_dump() for item in payload.items],
            payload.butcher_name,
            payload.notes,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    
    items = [
        CuttingItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product.name if item.product else "",
            output_weight=item.output_weight,
            waste_weight=item.waste_weight,
        )
        for item in order.items
    ]
    return CuttingOrderResponse(
        id=order.id,
        source_product_id=order.source_product_id,
        source_product_name=order.source_product.name if order.source_product else "",
        input_weight=order.input_weight,
        butcher_name=order.butcher_name,
        cutting_date=order.cutting_date,
        status=order.status,
        notes=order.notes,
        items=items,
        created_at=order.created_at,
    )


@router.patch("/orders/{order_id}/complete", response_model=CuttingOrderResponse)
def complete_cutting_order(
    order_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.INVENTORY_ADJUST)),
):
    service = CuttingService(db)
    try:
        order = service.complete_order(user.organization_id, order_id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    
    items = [
        CuttingItemResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product.name if item.product else "",
            output_weight=item.output_weight,
            waste_weight=item.waste_weight,
        )
        for item in order.items
    ]
    return CuttingOrderResponse(
        id=order.id,
        source_product_id=order.source_product_id,
        source_product_name=order.source_product.name if order.source_product else "",
        input_weight=order.input_weight,
        butcher_name=order.butcher_name,
        cutting_date=order.cutting_date,
        status=order.status,
        notes=order.notes,
        items=items,
        created_at=order.created_at,
    )
