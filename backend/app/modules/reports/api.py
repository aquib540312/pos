from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.reports.schemas import GSTR1LineRow, SalesSummaryResponse, StockSummaryRow
from app.modules.reports.service import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/sales-summary", response_model=SalesSummaryResponse)
def sales_summary(
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    return ReportService(db).sales_summary(user.organization_id, start, end)


@router.get("/stock-summary", response_model=list[StockSummaryRow])
def stock_summary(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.REPORTS_VIEW))):
    return ReportService(db).stock_summary(user.organization_id)


@router.get("/gstr1", response_model=list[GSTR1LineRow])
def gstr1(
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    return ReportService(db).gstr1_summary(user.organization_id, start, end)
