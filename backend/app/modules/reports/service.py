import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import HSNCode, Product
from app.models.inventory import StockItem
from app.models.sales import SalesInvoice, SalesInvoiceItem
from app.modules.reports.schemas import GSTR1LineRow, SalesSummaryResponse, StockSummaryRow


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
