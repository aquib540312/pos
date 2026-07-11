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
