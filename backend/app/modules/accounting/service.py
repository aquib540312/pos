from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine
from app.models.billing import Payment
from app.models.sales import SalesInvoice
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


class AccountingService:
    def __init__(self, db: Session):
        self.db = db
        self.ledger = LedgerRepository(db)

    def post_sale_invoice(self, invoice: SalesInvoice, payments: list[Payment], credit_shortfall: float) -> JournalEntry:
        """Double-entry posting for a completed sale.

        Debit side: cash/bank/receivable, split by how it was actually paid.
        Credit side: GST payable accounts at their exact stored amounts,
        rounding off as its own line, and Sales Revenue as the balancing
        plug (grand_total net of tax and rounding -- which is also net of
        any loyalty-point discount applied, since that discount already
        reduced grand_total before this posting happens).
        """
        self.ledger.ensure_default_accounts(invoice.organization_id)

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

        entry = self.ledger.add_entry(
            JournalEntry(
                organization_id=invoice.organization_id,
                entry_date=invoice.invoice_date.date(),
                reference_type="sales_invoice",
                reference_id=invoice.id,
                narration=f"Sale {invoice.invoice_number}",
            )
        )
        for code, amount in debits.items():
            if amount:
                account = self.ledger.get_by_code(invoice.organization_id, code)
                self.ledger.add_line(JournalLine(entry_id=entry.id, account_id=account.id, debit=round(amount, 2), credit=0))
        for code, amount in credits.items():
            if amount:
                account = self.ledger.get_by_code(invoice.organization_id, code)
                self.ledger.add_line(JournalLine(entry_id=entry.id, account_id=account.id, debit=0, credit=round(amount, 2)))
        return entry
