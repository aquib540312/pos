import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import require_permission
from app.core.permissions import Perm
from app.db.session import get_db
from app.models.rbac import User
from app.modules.reports.schemas import (
    BalanceSheetResponse,
    CashierSalesRow,
    DashboardResponse,
    ExpiringStockRow,
    GSTR1LineRow,
    LowStockRow,
    PaymentMethodBreakdownRow,
    ProfitAndLossResponse,
    SalesSummaryResponse,
    StockLedgerRow,
    StockSummaryRow,
    StockValuationRow,
    TopProductRow,
)
from app.modules.reports.service import ReportService

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.REPORTS_VIEW))):
    result = ReportService(db).dashboard(user.organization_id)
    db.commit()
    return result


@router.get("/expiring-stock", response_model=list[ExpiringStockRow])
def expiring_stock(
    within_days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    return ReportService(db).expiring_stock(user.organization_id, within_days)


@router.get("/low-stock", response_model=list[LowStockRow])
def low_stock(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.REPORTS_VIEW))):
    return ReportService(db).low_stock(user.organization_id)


@router.get("/stock-valuation", response_model=list[StockValuationRow])
def stock_valuation(db: Session = Depends(get_db), user: User = Depends(require_permission(Perm.REPORTS_VIEW))):
    return ReportService(db).stock_valuation(user.organization_id)


@router.get("/stock-ledger", response_model=list[StockLedgerRow])
def stock_ledger(
    product_id: uuid.UUID = Query(...),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    return ReportService(db).stock_ledger(user.organization_id, product_id, limit)


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


@router.get("/profit-and-loss", response_model=ProfitAndLossResponse)
def profit_and_loss(
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    return ReportService(db).profit_and_loss(user.organization_id, start, end)


@router.get("/balance-sheet", response_model=BalanceSheetResponse)
def balance_sheet(
    as_of: date = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    return ReportService(db).balance_sheet(user.organization_id, as_of)


@router.get("/top-products", response_model=list[TopProductRow])
def top_products(
    start: date = Query(...),
    end: date = Query(...),
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    return ReportService(db).top_products(user.organization_id, start, end, limit)


@router.get("/payment-breakdown", response_model=list[PaymentMethodBreakdownRow])
def payment_breakdown(
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    return ReportService(db).payment_method_breakdown(user.organization_id, start, end)


@router.get("/sales-by-cashier", response_model=list[CashierSalesRow])
def sales_by_cashier(
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Perm.REPORTS_VIEW)),
):
    return ReportService(db).sales_by_cashier(user.organization_id, start, end)
