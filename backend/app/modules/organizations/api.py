from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.organization import Branch
from app.models.rbac import User
from app.modules.organizations.schemas import BranchResponse
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


@router.get("/features", response_model=FeatureFlagsResponse)
def get_feature_flags(user: User = Depends(get_current_user)) -> FeatureFlagsResponse:
    """Lets the frontend show/hide integration-dependent UI (the UPI QR
    payment option, print-to-hardware actions) without a redeploy --
    flip POS_RAZORPAY_UPI_ENABLED / POS_PRINTER_ENABLED and reload."""
    settings = get_settings()
    return FeatureFlagsResponse(
        razorpay_upi_enabled=settings.razorpay_upi_enabled, printer_enabled=settings.printer_enabled
    )
