import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine
from app.models.billing import Payment
from app.models.purchasing import GoodsReceipt
from app.models.sales import SalesInvoice, SalesReturn
from app.modules.accounting.repository import LedgerRepository

# Payment method -> control account code it settles into. Card/UPI/wallet
# all land in "Bank" pending aggregator settlement -- splitting them into
# separate clearing accounts per gateway is a Phase 2 refinement once a
# real payment aggregator is wired up (see ROADMAP.md).
_PAYMENT_METHOD_ACCOUNT = {
    "cash": "1000",
    "card": "1010",
    "upi": "1010",
    "wallet": "1010",
    "gift_card": "1010",
    "credit": "1100",
}

# Refund mode -> control account credited when money/credit actually leaves
# the business on a return. "credit_note" reduces what the customer owes
# (Accounts Receivable) instead of paying out cash/bank.
_REFUND_MODE_ACCOUNT = {
    "cash": "1000",
    "card": "1010",
    "upi": "1010",
    "wallet": "1010",
    "credit_note": "1100",
}


class AccountingService:
    def __init__(self, db: Session):
        self.db = db
        self.ledger = LedgerRepository(db)

    def _post_entry(
        self,
        organization_id: uuid.UUID,
        entry_date: date,
        reference_type: str,
        reference_id: uuid.UUID,
        narration: str,
        debits: dict[str, float],
        credits: dict[str, float],
    ) -> JournalEntry:
        self.ledger.ensure_default_accounts(organization_id)
        entry = self.ledger.add_entry(
            JournalEntry(
                organization_id=organization_id,
                entry_date=entry_date,
                reference_type=reference_type,
                reference_id=reference_id,
                narration=narration,
            )
        )
        for code, amount in debits.items():
            if amount:
                account = self.ledger.get_by_code(organization_id, code)
                self.ledger.add_line(JournalLine(entry_id=entry.id, account_id=account.id, debit=round(amount, 2), credit=0))
        for code, amount in credits.items():
            if amount:
                account = self.ledger.get_by_code(organization_id, code)
                self.ledger.add_line(JournalLine(entry_id=entry.id, account_id=account.id, debit=0, credit=round(amount, 2)))
        return entry

    def post_sale_invoice(self, invoice: SalesInvoice, payments: list[Payment], credit_shortfall: float) -> JournalEntry:
        """Double-entry posting for a completed sale.

        Debit side: cash/bank/receivable, split by how it was actually paid.
        Credit side: GST payable accounts at their exact stored amounts,
        rounding off as its own line, and Sales Revenue as the balancing
        plug (grand_total net of tax and rounding -- which is also net of
        any loyalty-point discount applied, since that discount already
        reduced grand_total before this posting happens).
        """
        debits: dict[str, float] = defaultdict(float)
        for payment in payments:
            account_code = _PAYMENT_METHOD_ACCOUNT.get(payment.method, "1010")
            debits[account_code] += float(payment.amount)
        if credit_shortfall > 0:
            debits["1100"] += credit_shortfall

        credits: dict[str, float] = defaultdict(float)
        if invoice.cgst_total:
            credits["2100"] += float(invoice.cgst_total)
        if invoice.sgst_total:
            credits["2110"] += float(invoice.sgst_total)
        if invoice.igst_total:
            credits["2120"] += float(invoice.igst_total)

        revenue_plug = (
            float(invoice.grand_total)
            - float(invoice.cgst_total)
            - float(invoice.sgst_total)
            - float(invoice.igst_total)
            - float(invoice.round_off)
        )
        credits["4000"] += revenue_plug
        if invoice.round_off > 0:
            credits["4900"] += float(invoice.round_off)
        elif invoice.round_off < 0:
            debits["4900"] += -float(invoice.round_off)

        return self._post_entry(
            invoice.organization_id, invoice.invoice_date.date(), "sales_invoice", invoice.id,
            f"Sale {invoice.invoice_number}", dict(debits), dict(credits),
        )

    def post_goods_receipt(self, grn: GoodsReceipt, total_cost: float) -> JournalEntry:
        """Debit Inventory at cost, credit Accounts Payable for the same
        amount. Simplification (see ROADMAP.md): purchase-side GST input
        credit is not posted here because purchase order / GRN line items
        don't carry HSN/tax-rate data yet -- only the ex-tax cost is
        booked. Adding purchase-side tax fields is a prerequisite for
        claiming Input CGST/SGST/IGST credit correctly.
        """
        if total_cost <= 0:
            raise ValueError("total_cost must be positive")
        return self._post_entry(
            grn.organization_id, grn.received_at.date(), "goods_receipt", grn.id,
            f"Goods receipt {grn.grn_number}", {"1200": total_cost}, {"2000": total_cost},
        )

    def post_sales_return(self, sales_return: SalesReturn) -> JournalEntry:
        """Reverses the taxable value and GST of the returned lines, and
        credits whatever account the refund actually left through (cash/
        bank immediately, or Accounts Receivable if refunded as a credit
        note against a running customer balance)."""
        taxable = sum(float(i.taxable_value) for i in sales_return.items)
        cgst = sum(float(i.cgst_amount) for i in sales_return.items)
        sgst = sum(float(i.sgst_amount) for i in sales_return.items)
        igst = sum(float(i.igst_amount) for i in sales_return.items)

        debits: dict[str, float] = defaultdict(float)
        debits["5900"] += taxable
        if cgst:
            debits["2100"] += cgst
        if sgst:
            debits["2110"] += sgst
        if igst:
            debits["2120"] += igst

        refund_account = _REFUND_MODE_ACCOUNT.get(sales_return.refund_mode, "1000")
        credits = {refund_account: float(sales_return.refund_total)}

        return self._post_entry(
            sales_return.organization_id, sales_return.return_date.date(), "sales_return", sales_return.id,
            f"Return {sales_return.return_number}", dict(debits), credits,
        )
