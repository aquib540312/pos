import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine, LedgerAccount
from app.models.catalog import HSNCode, Product
from app.models.inventory import StockItem
from app.models.sales import SalesInvoice, SalesInvoiceItem
from app.modules.reports.schemas import (
    BalanceSheetResponse,
    GSTR1LineRow,
    LedgerAccountLine,
    ProfitAndLossResponse,
    SalesSummaryResponse,
    StockSummaryRow,
)


class ReportService:
    def __init__(self, db: Session):
        self.db = db

    def sales_summary(self, organization_id: uuid.UUID, start: date, end: date) -> SalesSummaryResponse:
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
        stmt = select(
            func.count(SalesInvoice.id),
            func.coalesce(func.sum(SalesInvoice.taxable_total), 0),
            func.coalesce(func.sum(SalesInvoice.cgst_total), 0),
            func.coalesce(func.sum(SalesInvoice.sgst_total), 0),
            func.coalesce(func.sum(SalesInvoice.igst_total), 0),
            func.coalesce(func.sum(SalesInvoice.cess_total), 0),
            func.coalesce(func.sum(SalesInvoice.grand_total), 0),
        ).where(
            SalesInvoice.organization_id == organization_id,
            SalesInvoice.status == "posted",
            SalesInvoice.invoice_date >= start_dt,
            SalesInvoice.invoice_date <= end_dt,
        )
        count, taxable, cgst, sgst, igst, cess, grand = self.db.execute(stmt).one()
        return SalesSummaryResponse(
            period_start=start,
            period_end=end,
            invoice_count=count,
            total_taxable_value=float(taxable),
            total_cgst=float(cgst),
            total_sgst=float(sgst),
            total_igst=float(igst),
            total_cess=float(cess),
            total_grand_total=float(grand),
        )

    def stock_summary(self, organization_id: uuid.UUID) -> list[StockSummaryRow]:
        stmt = (
            select(
                Product.id,
                Product.name,
                Product.sku,
                Product.reorder_level,
                func.coalesce(func.sum(StockItem.quantity_on_hand), 0),
            )
            .outerjoin(StockItem, StockItem.product_id == Product.id)
            .where(Product.organization_id == organization_id, Product.is_active.is_(True))
            .group_by(Product.id, Product.name, Product.sku, Product.reorder_level)
        )
        rows = []
        for product_id, name, sku, reorder_level, qty in self.db.execute(stmt).all():
            qty = float(qty)
            rows.append(
                StockSummaryRow(
                    product_id=product_id,
                    product_name=name,
                    sku=sku,
                    quantity_on_hand=qty,
                    reorder_level=float(reorder_level),
                    below_reorder=qty < float(reorder_level),
                )
            )
        return rows

    def gstr1_summary(self, organization_id: uuid.UUID, start: date, end: date) -> list[GSTR1LineRow]:
        """Line-level data grouped exactly as GSTR-1 HSN summary (Table 12)
        expects it: by HSN code + effective rate. This is the data, not the
        government JSON/upload format -- see ROADMAP.md for the GSP filing
        integration that would consume this."""
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
        stmt = (
            select(
                HSNCode.code,
                SalesInvoiceItem.tax_rate_percent,
                func.sum(SalesInvoiceItem.taxable_value),
                func.sum(SalesInvoiceItem.cgst_amount),
                func.sum(SalesInvoiceItem.sgst_amount),
                func.sum(SalesInvoiceItem.igst_amount),
                func.sum(SalesInvoiceItem.cess_amount),
                func.count(func.distinct(SalesInvoiceItem.invoice_id)),
            )
            .join(SalesInvoice, SalesInvoice.id == SalesInvoiceItem.invoice_id)
            .join(HSNCode, HSNCode.id == SalesInvoiceItem.hsn_code_id)
            .where(
                SalesInvoice.organization_id == organization_id,
                SalesInvoice.status == "posted",
                SalesInvoice.invoice_date >= start_dt,
                SalesInvoice.invoice_date <= end_dt,
            )
            .group_by(HSNCode.code, SalesInvoiceItem.tax_rate_percent)
        )
        return [
            GSTR1LineRow(
                hsn_code=hsn_code,
                tax_rate_percent=float(rate),
                taxable_value=float(taxable),
                cgst=float(cgst),
                sgst=float(sgst),
                igst=float(igst),
                cess=float(cess),
                invoice_count=count,
            )
            for hsn_code, rate, taxable, cgst, sgst, igst, cess, count in self.db.execute(stmt).all()
        ]

    def _account_balances(
        self, organization_id: uuid.UUID, account_type: str, *, start: date | None = None, end: date
    ) -> list[tuple[LedgerAccount, float, float]]:
        """Sum debit/credit per account of a given type, for entries dated
        on or before `end` (and on/after `start` if given -- P&L wants a
        date range, Balance Sheet wants everything up to a point in time)."""
        stmt = (
            select(
                LedgerAccount,
                func.coalesce(func.sum(JournalLine.debit), 0),
                func.coalesce(func.sum(JournalLine.credit), 0),
            )
            .join(JournalLine, JournalLine.account_id == LedgerAccount.id)
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(
                LedgerAccount.organization_id == organization_id,
                LedgerAccount.account_type == account_type,
                JournalEntry.entry_date <= end,
            )
            .group_by(LedgerAccount.id)
        )
        if start is not None:
            stmt = stmt.where(JournalEntry.entry_date >= start)
        return [(account, float(debit), float(credit)) for account, debit, credit in self.db.execute(stmt).all()]

    def profit_and_loss(self, organization_id: uuid.UUID, start: date, end: date) -> ProfitAndLossResponse:
        """Income and expense accounts have opposite normal balances:
        income accounts grow on the credit side (a sale credits Sales
        Revenue), expense accounts grow on the debit side (a purchase
        debits Purchases, a return debits Sales Returns) -- so each is
        reported as (credit - debit) or (debit - credit) respectively,
        never a raw balance."""
        income_lines = [
            LedgerAccountLine(account_code=a.code, account_name=a.name, amount=round(credit - debit, 2))
            for a, debit, credit in self._account_balances(organization_id, "income", start=start, end=end)
            if round(credit - debit, 2) != 0
        ]
        expense_lines = [
            LedgerAccountLine(account_code=a.code, account_name=a.name, amount=round(debit - credit, 2))
            for a, debit, credit in self._account_balances(organization_id, "expense", start=start, end=end)
            if round(debit - credit, 2) != 0
        ]
        total_income = round(sum(line.amount for line in income_lines), 2)
        total_expense = round(sum(line.amount for line in expense_lines), 2)
        return ProfitAndLossResponse(
            period_start=start,
            period_end=end,
            income_lines=income_lines,
            expense_lines=expense_lines,
            total_income=total_income,
            total_expense=total_expense,
            net_profit=round(total_income - total_expense, 2),
        )

    def balance_sheet(self, organization_id: uuid.UUID, as_of: date) -> BalanceSheetResponse:
        """Assets carry a debit normal balance, liabilities and equity a
        credit normal balance. Retained earnings (net profit since
        inception, not yet formally closed into an equity account by a
        year-end closing entry) is added to equity as its own derived
        line so total_assets == total_liabilities + total_equity holds --
        this is standard practice for an interim/unclosed balance sheet.
        """
        asset_lines = [
            LedgerAccountLine(account_code=a.code, account_name=a.name, amount=round(debit - credit, 2))
            for a, debit, credit in self._account_balances(organization_id, "asset", end=as_of)
            if round(debit - credit, 2) != 0
        ]
        liability_lines = [
            LedgerAccountLine(account_code=a.code, account_name=a.name, amount=round(credit - debit, 2))
            for a, debit, credit in self._account_balances(organization_id, "liability", end=as_of)
            if round(credit - debit, 2) != 0
        ]
        equity_lines = [
            LedgerAccountLine(account_code=a.code, account_name=a.name, amount=round(credit - debit, 2))
            for a, debit, credit in self._account_balances(organization_id, "equity", end=as_of)
            if round(credit - debit, 2) != 0
        ]

        income_to_date = sum(
            round(credit - debit, 2) for _, debit, credit in self._account_balances(organization_id, "income", end=as_of)
        )
        expense_to_date = sum(
            round(debit - credit, 2) for _, debit, credit in self._account_balances(organization_id, "expense", end=as_of)
        )
        retained_earnings = round(income_to_date - expense_to_date, 2)

        total_assets = round(sum(line.amount for line in asset_lines), 2)
        total_liabilities = round(sum(line.amount for line in liability_lines), 2)
        total_equity = round(sum(line.amount for line in equity_lines) + retained_earnings, 2)

        return BalanceSheetResponse(
            as_of=as_of,
            asset_lines=asset_lines,
            liability_lines=liability_lines,
            equity_lines=equity_lines,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
            retained_earnings=retained_earnings,
        )
