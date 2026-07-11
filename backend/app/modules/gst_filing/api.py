import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.exceptions import NotFoundError, ValidationError
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.organization import Organization
from app.models.rbac import User
from app.modules.gst_filing.schemas import GSTR1FilingResponse, GSTR1PayloadResponse
from app.modules.gst_filing.service import GSTFilingService

router = APIRouter(prefix="/api/v1/gst-filing", tags=["gst-filing"])


def _organization_gstin(db: Session, user: User) -> str:
    org = db.get(Organization, user.organization_id)
    if org is None or not org.gstin:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Organization has no GSTIN configured in company settings"
        )
    return org.gstin


@router.post("/gstr1/{return_period}/generate", response_model=GSTR1PayloadResponse)
def generate_gstr1(
    return_period: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    gstin = _organization_gstin(db, user)
    try:
        filing = GSTFilingService(db).generate_gstr1(user.organization_id, return_period, gstin)
        db.commit()
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return GSTR1PayloadResponse(return_period=return_period, status=filing.status, payload=json.loads(filing.payload_json))


@router.get("/gstr1/{return_period}", response_model=GSTR1FilingResponse)
def get_gstr1_filing(
    return_period: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    filing = GSTFilingService(db).filings.get_by_period(user.organization_id, return_period)
    if filing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No GSTR-1 filing for period {return_period}")
    return filing


@router.post("/gstr1/{return_period}/submit", response_model=GSTR1FilingResponse)
def submit_gstr1(
    return_period: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    gstin = _organization_gstin(db, user)
    service = GSTFilingService(db)
    try:
        filing = service.submit_gstr1(user.organization_id, return_period, gstin)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return filing


@router.get("/gstr1/{return_period}/status", response_model=GSTR1FilingResponse)
def check_gstr1_status(
    return_period: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    try:
        filing = GSTFilingService(db).check_status(user.organization_id, return_period)
        db.commit()
    except NotFoundError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return filing
