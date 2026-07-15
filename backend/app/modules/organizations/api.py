import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.deps import get_current_user, require_permission
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.organization import Branch
from app.models.rbac import User
from app.modules.organizations.schemas import (
    BranchCreateRequest,
    BranchResponse,
    WarehouseCreateRequest,
    WarehouseResponse,
)
from app.modules.organizations.service import OrganizationService
from app.modules.payments.schemas import FeatureFlagsResponse

router = APIRouter(prefix="/api/v1/org", tags=["organizations"])


@router.get("/branches", response_model=list[BranchResponse])
def list_branches(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = (
        select(Branch)
        .where(Branch.organization_id == user.organization_id, Branch.is_active.is_(True))
        .options(selectinload(Branch.warehouses))
    )
    return list(db.execute(stmt).scalars())


@router.post("/branches", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
def create_branch(
    payload: BranchCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.ORG_MANAGE)),
):
    try:
        branch = OrganizationService(db).create_branch(
            user.organization_id, payload.code, payload.name, payload.business_type,
            payload.state_code, payload.gstin, payload.address,
        )
        db.commit()
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return branch


@router.post(
    "/branches/{branch_id}/warehouses", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED
)
def create_warehouse(
    branch_id: uuid.UUID,
    payload: WarehouseCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.ORG_MANAGE)),
):
    try:
        warehouse = OrganizationService(db).create_warehouse(
            user.organization_id, branch_id, payload.code, payload.name, payload.is_default
        )
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    return warehouse


@router.get("/features", response_model=FeatureFlagsResponse)
def get_feature_flags(user: User = Depends(get_current_user)) -> FeatureFlagsResponse:
    """Lets the frontend show/hide integration-dependent UI (the UPI QR
    payment option, print-to-hardware actions) without a redeploy --
    flip POS_RAZORPAY_UPI_ENABLED / POS_PRINTER_ENABLED and reload."""
    settings = get_settings()
    return FeatureFlagsResponse(
        razorpay_upi_enabled=settings.razorpay_upi_enabled, printer_enabled=settings.printer_enabled
    )
