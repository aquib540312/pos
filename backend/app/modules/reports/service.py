import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine, LedgerAccount
from app.models.billing import Payment, Shift
from app.models.catalog import HSNCode, Product, ProductBatch, UnitOfMeasure
from app.models.inventory import StockItem, StockLedgerEntry
from app.models.organization import Warehouse
from app.models.party import Customer
from app.models.rbac import User
from app.models.sales import SalesInvoice, SalesInvoiceItem
from app.models.sync import SyncConflict
from app.modules.gst_filing.schema_builder import B2BInvoiceLine, B2BInvoiceRateItem, B2CSLine
from app.modules.notifications.service import NotificationService
from app.modules.reports.schemas import (
    BalanceSheetResponse,
    CashierSalesRow,
    DashboardResponse,
    ExpiringStockRow,
    GSTR1LineRow,
    LedgerAccountLine,
    LowStockRow,
    PaymentMethodBreakdownRow,
    ProfitAndLossResponse,
    SalesSummaryResponse,
    StockLedgerRow,
    StockSummaryRow,
    StockValuationRow,
    TopProductRow,
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

    def gstr1_b2cs_summary(self, organization_id: uuid.UUID, start: date, end: date) -> list[B2CSLine]:
        """GSTR-1 Table 7 (B2C small) grouping: by place of supply, intra-
        vs inter-state, and rate. Only sales with no buyer GSTIN captured
        (walk-in/unregistered consumers) belong here -- registered-buyer
        sales are reported invoice-wise instead, see `gstr1_b2b_summary`."""
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
        stmt = (
            select(
                SalesInvoice.place_of_supply_state_code,
                SalesInvoice.is_inter_state,
                SalesInvoiceItem.tax_rate_percent,
                func.sum(SalesInvoiceItem.taxable_value),
                func.sum(SalesInvoiceItem.cgst_amount),
                func.sum(SalesInvoiceItem.sgst_amount),
                func.sum(SalesInvoiceItem.igst_amount),
                func.sum(SalesInvoiceItem.cess_amount),
            )
            .join(SalesInvoice, SalesInvoice.id == SalesInvoiceItem.invoice_id)
            .where(
                SalesInvoice.organization_id == organization_id,
                SalesInvoice.status == "posted",
                SalesInvoice.invoice_date >= start_dt,
                SalesInvoice.invoice_date <= end_dt,
                SalesInvoice.customer_gstin.is_(None),
            )
            .group_by(SalesInvoice.place_of_supply_state_code, SalesInvoice.is_inter_state, SalesInvoiceItem.tax_rate_percent)
        )
        return [
            B2CSLine(
                place_of_supply_state_code=pos,
                is_inter_state=is_inter_state,
                tax_rate_percent=float(rate),
                taxable_value=float(taxable),
                cgst=float(cgst),
                sgst=float(sgst),
                igst=float(igst),
                cess=float(cess),
            )
            for pos, is_inter_state, rate, taxable, cgst, sgst, igst, cess in self.db.execute(stmt).all()
        ]

    def gstr1_b2b_summary(self, organization_id: uuid.UUID, start: date, end: date) -> list[B2BInvoiceLine]:
        """GSTR-1 Table 4 (B2B), invoice-wise: every sale with a buyer
        GSTIN captured at posting time, one entry per invoice with a
        rate-item per distinct tax rate on that invoice (an invoice can
        mix rates, e.g. 5% and 18% products in the same cart)."""
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
        stmt = (
            select(
                SalesInvoice.id,
                SalesInvoice.customer_gstin,
                SalesInvoice.invoice_number,
                SalesInvoice.invoice_date,
                SalesInvoice.grand_total,
                SalesInvoice.place_of_supply_state_code,
                SalesInvoice.is_inter_state,
                SalesInvoiceItem.tax_rate_percent,
                func.sum(SalesInvoiceItem.taxable_value),
                func.sum(SalesInvoiceItem.cgst_amount),
                func.sum(SalesInvoiceItem.sgst_amount),
                func.sum(SalesInvoiceItem.igst_amount),
                func.sum(SalesInvoiceItem.cess_amount),
            )
            .join(SalesInvoice, SalesInvoice.id == SalesInvoiceItem.invoice_id)
            .where(
                SalesInvoice.organization_id == organization_id,
                SalesInvoice.status == "posted",
                SalesInvoice.invoice_date >= start_dt,
                SalesInvoice.invoice_date <= end_dt,
                SalesInvoice.customer_gstin.is_not(None),
            )
            .group_by(
                SalesInvoice.id,
                SalesInvoice.customer_gstin,
                SalesInvoice.invoice_number,
                SalesInvoice.invoice_date,
                SalesInvoice.grand_total,
                SalesInvoice.place_of_supply_state_code,
                SalesInvoice.is_inter_state,
                SalesInvoiceItem.tax_rate_percent,
            )
            .order_by(SalesInvoice.invoice_number)
        )

        invoices: dict[uuid.UUID, B2BInvoiceLine] = {}
        for (
            invoice_id, gstin, invoice_number, invoice_date, grand_total, pos, is_inter_state,
            rate, taxable, cgst, sgst, igst, cess,
        ) in self.db.execute(stmt).all():
            rate_item = B2BInvoiceRateItem(
                tax_rate_percent=float(rate),
                taxable_value=float(taxable),
                cgst=float(cgst),
                sgst=float(sgst),
                igst=float(igst),
                cess=float(cess),
            )
            if invoice_id not in invoices:
                invoices[invoice_id] = B2BInvoiceLine(
                    buyer_gstin=gstin,
                    invoice_number=invoice_number,
                    invoice_date=invoice_date.strftime("%d-%m-%Y"),
                    invoice_value=float(grand_total),
                    place_of_supply_state_code=pos,
                    is_inter_state=is_inter_state,
                    rate_items=[rate_item],
                )
            else:
                invoices[invoice_id].rate_items.append(rate_item)
        return list(invoices.values())

    def gross_turnover(self, organization_id: uuid.UUID, start: date, end: date) -> float:
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
        stmt = select(func.coalesce(func.sum(SalesInvoice.grand_total), 0)).where(
            SalesInvoice.organization_id == organization_id,
            SalesInvoice.status == "posted",
            SalesInvoice.invoice_date >= start_dt,
            SalesInvoice.invoice_date <= end_dt,
        )
        return float(self.db.execute(stmt).scalar_one())

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

    def top_products(self, organization_id: uuid.UUID, start: date, end: date, limit: int = 10) -> list[TopProductRow]:
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
        stmt = (
            select(
                Product.id,
                Product.name,
                Product.sku,
                func.coalesce(func.sum(SalesInvoiceItem.quantity), 0),
                func.coalesce(func.sum(SalesInvoiceItem.line_total), 0),
            )
            .join(SalesInvoiceItem, SalesInvoiceItem.product_id == Product.id)
            .join(SalesInvoice, SalesInvoice.id == SalesInvoiceItem.invoice_id)
            .where(
                SalesInvoice.organization_id == organization_id,
                SalesInvoice.status == "posted",
                SalesInvoice.invoice_date >= start_dt,
                SalesInvoice.invoice_date <= end_dt,
            )
            .group_by(Product.id, Product.name, Product.sku)
            .order_by(func.coalesce(func.sum(SalesInvoiceItem.line_total), 0).desc())
            .limit(limit)
        )
        return [
            TopProductRow(product_id=pid, product_name=name, sku=sku, quantity_sold=float(qty), revenue=float(revenue))
            for pid, name, sku, qty, revenue in self.db.execute(stmt).all()
        ]

    def payment_method_breakdown(
        self, organization_id: uuid.UUID, start: date, end: date
    ) -> list[PaymentMethodBreakdownRow]:
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
        stmt = (
            select(Payment.method, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
            .join(SalesInvoice, SalesInvoice.id == Payment.invoice_id)
            .where(
                SalesInvoice.organization_id == organization_id,
                SalesInvoice.status == "posted",
                SalesInvoice.invoice_date >= start_dt,
                SalesInvoice.invoice_date <= end_dt,
            )
            .group_by(Payment.method)
            .order_by(func.coalesce(func.sum(Payment.amount), 0).desc())
        )
        return [
            PaymentMethodBreakdownRow(method=method, payment_count=count, total_amount=float(total))
            for method, count, total in self.db.execute(stmt).all()
        ]

    def sales_by_cashier(self, organization_id: uuid.UUID, start: date, end: date) -> list[CashierSalesRow]:
        """Only invoices posted within a shift are attributable to a
        cashier -- a shift-less invoice (e.g. posted outside till
        operations) has no cashier to credit it to, so it's excluded here
        rather than lumped under some placeholder."""
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
        stmt = (
            select(
                User.id,
                User.full_name,
                func.count(SalesInvoice.id),
                func.coalesce(func.sum(SalesInvoice.grand_total), 0),
            )
            .join(Shift, Shift.id == SalesInvoice.shift_id)
            .join(User, User.id == Shift.user_id)
            .where(
                SalesInvoice.organization_id == organization_id,
                SalesInvoice.status == "posted",
                SalesInvoice.invoice_date >= start_dt,
                SalesInvoice.invoice_date <= end_dt,
            )
            .group_by(User.id, User.full_name)
            .order_by(func.coalesce(func.sum(SalesInvoice.grand_total), 0).desc())
        )
        return [
            CashierSalesRow(user_id=uid, user_name=name, invoice_count=count, total_grand_total=float(total))
            for uid, name, count, total in self.db.execute(stmt).all()
        ]

    def expiring_stock(self, organization_id: uuid.UUID, within_days: int) -> list[ExpiringStockRow]:
        """Batches whose expiry is <= `within_days` from today (or already
        expired), with positive on-hand quantity at some warehouse."""
        cutoff = date.today() + timedelta(days=within_days)
        stmt = (
            select(
                Product.id,
                Product.name,
                Product.sku,
                StockItem.warehouse_id,
                Warehouse.name,
                StockItem.batch_id,
                ProductBatch.batch_number,
                StockItem.quantity_on_hand,
                ProductBatch.expiry_date,
            )
            .join(ProductBatch, ProductBatch.id == StockItem.batch_id)
            .join(Product, Product.id == ProductBatch.product_id)
            .outerjoin(Warehouse, Warehouse.id == StockItem.warehouse_id)
            .where(
                StockItem.organization_id == organization_id,
                ProductBatch.expiry_date.is_not(None),
                ProductBatch.expiry_date <= cutoff,
                StockItem.quantity_on_hand > 0,
            )
            .order_by(ProductBatch.expiry_date.asc())
        )
        rows = []
        for pid, name, sku, wh_id, wh_name, batch_id, batch_number, qty, expiry in self.db.execute(stmt).all():
            days = (expiry - date.today()).days if expiry else None
            rows.append(
                ExpiringStockRow(
                    product_id=pid, product_name=name, sku=sku, warehouse_id=wh_id, warehouse_name=wh_name,
                    batch_id=batch_id, batch_number=batch_number, quantity_on_hand=float(qty),
                    expiry_date=expiry, days_to_expiry=days,
                )
            )
        return rows

    def low_stock(self, organization_id: uuid.UUID) -> list[LowStockRow]:
        """Products at or below their reorder level (the "below_reorder"
        flag the stock-summary report already computes, but packaged as a
        standalone actionable list -- only the products that need
        reordering, tagged with their UOM)."""
        stmt = (
            select(
                Product.id,
                Product.name,
                Product.sku,
                Product.barcode,
                UnitOfMeasure.code,
                func.coalesce(func.sum(StockItem.quantity_on_hand), 0),
                Product.reorder_level,
            )
            .outerjoin(StockItem, StockItem.product_id == Product.id)
            .outerjoin(UnitOfMeasure, UnitOfMeasure.id == Product.uom_id)
            .where(Product.organization_id == organization_id, Product.is_active.is_(True))
            .group_by(Product.id, Product.name, Product.sku, Product.barcode, UnitOfMeasure.code, Product.reorder_level)
        )
        rows = []
        for pid, name, sku, barcode, uom_code, qty, reorder in self.db.execute(stmt).all():
            qty = float(qty)
            reorder = float(reorder)
            if qty <= reorder:
                rows.append(
                    LowStockRow(
                        product_id=pid, product_name=name, sku=sku, barcode=barcode, uom_code=uom_code,
                        quantity_on_hand=qty, reorder_level=reorder, below_reorder=qty <= reorder,
                    )
                )
        return rows

    def stock_valuation(self, organization_id: uuid.UUID) -> list[StockValuationRow]:
        """On-hand quantity x the product's purchase price (approximate
        cost) per product, plus the aggrated valuation. The purchase-price
        proxy is a deliberate simplification -- a proper weighted-average
        cost would come from batch purchase_price, which is also available
        here but the product-level number is what a re-order decision needs."""
        stmt = (
            select(
                Product.id,
                Product.name,
                Product.sku,
                func.coalesce(func.sum(StockItem.quantity_on_hand), 0),
            )
            .outerjoin(StockItem, StockItem.product_id == Product.id)
            .where(Product.organization_id == organization_id, Product.is_active.is_(True))
            .group_by(Product.id, Product.name, Product.sku)
        )
        rows = []
        for pid, name, sku, qty in self.db.execute(stmt).all():
            qty = float(qty)
            if qty <= 0:
                continue
            product = self.db.get(Product, pid)
            average_cost = float(product.purchase_price) if product else 0
            rows.append(
                StockValuationRow(
                    product_id=pid, product_name=name, sku=sku, quantity_on_hand=qty,
                    average_cost=average_cost, valuation=round(qty * average_cost, 2),
                )
            )
        return rows

    def stock_ledger(self, organization_id: uuid.UUID, product_id: uuid.UUID, limit: int = 100) -> list[StockLedgerRow]:
        """Immutable stock-movement history for one product, newest first."""
        stmt = (
            select(StockLedgerEntry)
            .where(StockLedgerEntry.organization_id == organization_id, StockLedgerEntry.product_id == product_id)
            .order_by(StockLedgerEntry.created_at.desc())
            .limit(limit)
        )
        return [
            StockLedgerRow(
                id=e.id, created_at=e.created_at, warehouse_id=e.warehouse_id, product_id=e.product_id,
                batch_id=e.batch_id, movement_type=e.movement_type, quantity_delta=float(e.quantity_delta),
                reference_type=e.reference_type, reference_id=e.reference_id, notes=e.notes,
            )
            for e in self.db.execute(stmt).scalars().all()
        ]

    def dashboard(self, organization_id: uuid.UUID) -> DashboardResponse:
        """The numbers a till manager wants at a glance: today's sales,
        low-stock and expiring-stock counts, open shifts, and outstanding
        customer credit."""
        today = date.today()
        start_dt = datetime.combine(today, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(today, time.max, tzinfo=timezone.utc)

        stmt = select(
            func.count(SalesInvoice.id),
            func.coalesce(func.sum(SalesInvoice.taxable_total), 0),
            func.coalesce(func.sum(SalesInvoice.cgst_total + SalesInvoice.sgst_total + SalesInvoice.igst_total), 0),
            func.coalesce(func.sum(SalesInvoice.grand_total), 0),
        ).where(
            SalesInvoice.organization_id == organization_id,
            SalesInvoice.status == "posted",
            SalesInvoice.invoice_date >= start_dt,
            SalesInvoice.invoice_date <= end_dt,
        )
        inv_count, taxable, gst, grand = self.db.execute(stmt).one()

        cash_stmt = select(func.coalesce(func.sum(Payment.amount), 0)).join(
            SalesInvoice, SalesInvoice.id == Payment.invoice_id
        ).where(
            SalesInvoice.organization_id == organization_id,
            SalesInvoice.status == "posted",
            SalesInvoice.invoice_date >= start_dt,
            SalesInvoice.invoice_date <= end_dt,
            Payment.method == "cash",
        )
        cash_sales = self.db.execute(cash_stmt).scalar_one()

        low_count = len(self.low_stock(organization_id))
        expiring_count = len(self.expiring_stock(organization_id, within_days=30))
        self._sync_alert_notifications(organization_id)

        open_shifts = self.db.execute(
            select(func.count(Shift.id)).where(Shift.organization_id == organization_id, Shift.status == "open")
        ).scalar_one()

        credit_outstanding = self.db.execute(
            select(func.coalesce(func.sum(Customer.credit_balance), 0)).where(
                Customer.organization_id == organization_id, Customer.is_credit_customer.is_(True)
            )
        ).scalar_one()

        conflicts = self.db.execute(
            select(func.count(SyncConflict.id)).where(
                SyncConflict.organization_id == organization_id, SyncConflict.status == "open"
            )
        ).scalar_one()

        return DashboardResponse(
            today_invoice_count=inv_count,
            today_taxable_value=float(taxable),
            today_gst_total=float(gst),
            today_grand_total=float(grand),
            today_cash_sales=float(cash_sales),
            low_stock_count=low_count,
            expiring_soon_count=expiring_count,
            open_shifts=open_shifts,
            open_credit_outstanding=float(credit_outstanding),
            open_conflicts=conflicts,
        )

    def _sync_alert_notifications(self, organization_id: uuid.UUID) -> None:
        """Create in-app notifications for open dashboard alerts (low stock,
        expiring stock). Deduplicated per product in NotificationService, so
        the bell badge doesn't balloon on every dashboard load."""
        try:
            low_stock_rows = self.low_stock(organization_id)
            expiring_rows = self.expiring_stock(organization_id, within_days=30)
            NotificationService(self.db).sync_alerts(
                organization_id,
                [(r.product_id, r.product_name, r.sku, r.quantity_on_hand) for r in low_stock_rows],
                [
                    (r.product_id, r.product_name, r.sku, r.batch_number, r.days_to_expiry or 0)
                    for r in expiring_rows
                ],
            )
        except Exception:  # pragma: no cover - alert sync must never break the dashboard
            pass
