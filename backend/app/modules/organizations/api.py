import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.deps import get_current_user, require_permission
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.organization import Branch, Organization
from app.models.rbac import User
from app.modules.organizations.schemas import (
    BranchCreateRequest,
    BranchResponse,
    OrganizationProfileResponse,
    OrganizationProfileUpdateRequest,
    WarehouseCreateRequest,
    WarehouseResponse,
)
from app.modules.organizations.service import OrganizationService
from app.modules.payments.schemas import FeatureFlagsResponse

router = APIRouter(prefix="/api/v1/org", tags=["organizations"])

_ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_IMAGE_CONTENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def _profile_response(org: Organization) -> OrganizationProfileResponse:
    return OrganizationProfileResponse(
        id=org.id,
        legal_name=org.legal_name,
        trade_name=org.trade_name,
        gstin=org.gstin,
        pan=org.pan,
        default_state_code=org.default_state_code,
        phone=org.phone,
        address=org.address,
        footer_note=org.footer_note,
        tax_mode=org.tax_mode,
        has_logo=bool(org.logo_path),
        vat_number=org.gstin,
        qr_enabled=getattr(org, "qr_enabled", False),
    )


@router.get("/profile", response_model=OrganizationProfileResponse)
def get_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _profile_response(OrganizationService(db).get_org_or_404(user.organization_id))


@router.patch("/profile", response_model=OrganizationProfileResponse)
def update_profile(
    payload: OrganizationProfileUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.ORG_MANAGE)),
):
    from sqlalchemy.exc import IntegrityError

    try:
        org = OrganizationService(db).update_profile(
            user.organization_id, payload.model_dump(exclude_unset=True)
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "That GSTIN is already in use by another business") from exc
    return _profile_response(org)


@router.post("/logo", response_model=OrganizationProfileResponse)
async def upload_org_logo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.ORG_MANAGE)),
):
    """Store the business logo under the uploads dir and point the org at
    it. Served back via GET /org/logo.png (no auth header needed on the
    receipt page)."""
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _ALLOWED_IMAGE_EXTS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Logo must be PNG, JPG/JPEG or WebP")
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Logo must be 2 MB or smaller")

    org = OrganizationService(db).get_org_or_404(user.organization_id)
    upload_dir = get_settings().product_image_dir
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"org-{org.id}{ext}"
    with open(os.path.join(upload_dir, filename), "wb") as fh:
        fh.write(content)

    org.logo_path = filename
    db.commit()
    return _profile_response(org)


@router.get("/logo.png")
def get_org_logo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org = OrganizationService(db).get_org_or_404(user.organization_id)
    if not org.logo_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No logo uploaded")
    path = os.path.join(get_settings().product_image_dir, org.logo_path)
    if not os.path.exists(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Logo file is missing")
    ext = os.path.splitext(org.logo_path)[1].lower().lstrip(".")
    return Response(content=open(path, "rb").read(), media_type=_IMAGE_CONTENT_TYPES.get(ext, "application/octet-stream"))


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
