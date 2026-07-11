import uuid
from datetime import date

from pydantic import BaseModel


class SalesSummaryResponse(BaseModel):
    period_start: date
    period_end: date
    invoice_count: int
    total_taxable_value: float
    total_cgst: float
    total_sgst: float
    total_igst: float
    total_cess: float
    total_grand_total: float


class StockSummaryRow(BaseModel):
    product_id: uuid.UUID
    product_name: str
    sku: str
    quantity_on_hand: float
    reorder_level: float
    below_reorder: bool


class GSTR1LineRow(BaseModel):
    hsn_code: str
    tax_rate_percent: float
    taxable_value: float
    cgst: float
    sgst: float
    igst: float
    cess: float
    invoice_count: int


class LedgerAccountLine(BaseModel):
    account_code: str
    account_name: str
    amount: float


class ProfitAndLossResponse(BaseModel):
    period_start: date
    period_end: date
    income_lines: list[LedgerAccountLine]
    expense_lines: list[LedgerAccountLine]
    total_income: float
    total_expense: float
    net_profit: float


class BalanceSheetResponse(BaseModel):
    as_of: date
    asset_lines: list[LedgerAccountLine]
    liability_lines: list[LedgerAccountLine]
    equity_lines: list[LedgerAccountLine]
    total_assets: float
    total_liabilities: float
    total_equity: float
    retained_earnings: float


class TopProductRow(BaseModel):
    product_id: uuid.UUID
    product_name: str
    sku: str
    quantity_sold: float
    revenue: float


class PaymentMethodBreakdownRow(BaseModel):
    method: str
    payment_count: int
    total_amount: float


class CashierSalesRow(BaseModel):
    user_id: uuid.UUID
    user_name: str
    invoice_count: int
    total_grand_total: float
