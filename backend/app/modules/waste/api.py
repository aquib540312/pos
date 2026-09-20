from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.waste.schemas import WasteCreateRequest, WasteResponse
from app.modules.waste.service import WasteService

router = APIRouter(prefix="/api/v1/waste", tags=["waste"])


@router.get("", response_model=list[WasteResponse])
def list_waste(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.INVENTORY_VIEW)),
):
    entries = WasteService(db).list_waste(user.organization_id)
    result = []
    for entry in entries:
        resp = WasteResponse(
            id=entry.id,
            product_id=entry.product_id,
            product_name=entry.product.name if entry.product else "",
            quantity=entry.quantity,
            unit_cost=entry.unit_cost,
            total_cost=entry.total_cost,
            reason=entry.reason,
            notes=entry.notes,
            recorded_by=entry.recorded_by,
            created_at=entry.created_at,
        )
        result.append(resp)
    return result


@router.post("", response_model=WasteResponse, status_code=status.HTTP_201_CREATED)
def create_waste(
    payload: WasteCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.INVENTORY_ADJUST)),
):
    entry = WasteService(db).create_waste(
        user.organization_id, user.id,
        payload.product_id, payload.quantity, payload.unit_cost,
        payload.reason, payload.notes,
    )
    db.commit()
    return WasteResponse(
        id=entry.id,
        product_id=entry.product_id,
        product_name=entry.product.name if entry.product else "",
        quantity=entry.quantity,
        unit_cost=entry.unit_cost,
        total_cost=entry.total_cost,
        reason=entry.reason,
        notes=entry.notes,
        recorded_by=entry.recorded_by,
        created_at=entry.created_at,
    )
