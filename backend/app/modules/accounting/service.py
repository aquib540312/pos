import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationError
from app.models.accounting import JournalEntry, JournalLine, LedgerAccount
from app.models.billing import Payment
from app.models.purchasing import GoodsReceipt
from app.models.sales import SalesInvoice, SalesReturn
from app.modules.accounting.repository import LedgerRepository
from app.modules.accounting.schemas import (
    AccountLedgerLine,
    LedgerResponse,
    TrialBalanceLine,
    TrialBalanceResponse,
)

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

    def post_goods_receipt(
        self,
        grn: GoodsReceipt,
        total_cost: float,
        input_cgst: float = 0,
        input_sgst: float = 0,
        input_igst: float = 0,
    ) -> JournalEntry:
        """Debit Inventory at cost, credit Accounts Payable for the same
        amount. When the GRN lines carried HSN/tax data (see purchasing
        receive_goods), the GST component is ALSO debited to the appropriate
        Input CGST/SGST/IGST Receivable account -- this is what makes purchase-
        side input credit claimable in GSTR-3B (previously deferred because
        GRN lines had no tax fields)."""
        if total_cost <= 0:
            raise ValueError("total_cost must be positive")
        debits: dict[str, float] = defaultdict(float)
        debits["1200"] += total_cost
        if input_cgst:
            debits["2200"] += round(input_cgst, 2)
        if input_sgst:
            debits["2210"] += round(input_sgst, 2)
        if input_igst:
            debits["2220"] += round(input_igst, 2)
        credits = {"2000": round(total_cost + float(input_cgst) + float(input_sgst) + float(input_igst), 2)}
        return self._post_entry(
            grn.organization_id, grn.received_at.date(), "goods_receipt", grn.id,
            f"Goods receipt {grn.grn_number}", dict(debits), dict(credits),
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

    def post_sale_cancellation(self, invoice: SalesInvoice) -> JournalEntry:
        """Reverses the original sale's posting line-for-line: debit the
        same revenue / refund the GST payable accounts, credit the cash /
        bank / receivable accounts that the original payments debited.
        Balances to zero with the original sale entry (the round-off line
        is reversed with the opposite sign)."""
        debits: dict[str, float] = defaultdict(float)
        credits: dict[str, float] = defaultdict(float)
        revenue_plug = (
            float(invoice.grand_total)
            - float(invoice.cgst_total)
            - float(invoice.sgst_total)
            - float(invoice.igst_total)
            - float(invoice.round_off)
        )
        # Original sale credited revenue -> cancellation debits it back.
        debits["4000"] += revenue_plug
        if invoice.round_off > 0:
            debits["4900"] += float(invoice.round_off)
        elif invoice.round_off < 0:
            credits["4900"] += -float(invoice.round_off)

        if invoice.cgst_total:
            credits["2100"] += float(invoice.cgst_total)
        if invoice.sgst_total:
            credits["2110"] += float(invoice.sgst_total)
        if invoice.igst_total:
            credits["2120"] += float(invoice.igst_total)

        # Original sale debited cash/bank/receivable -> credit it back.
        for payment in invoice.payments:
            account_code = _PAYMENT_METHOD_ACCOUNT.get(payment.method, "1010")
            credits[account_code] += float(payment.amount)
        if invoice.is_credit_sale:
            shortfall = round(float(invoice.grand_total) - sum(float(p.amount) for p in invoice.payments), 2)
            if shortfall > 0:
                credits["1100"] += shortfall

        return self._post_entry(
            invoice.organization_id, invoice.invoice_date.date(), "sales_cancellation", invoice.id,
            f"Cancellation of {invoice.invoice_number}", dict(debits), dict(credits),
        )

    def post_supplier_payment(
        self, organization_id: uuid.UUID, supplier_id: uuid.UUID, supplier_payment_id: uuid.UUID,
        paid_at: date, amount: float, method: str, narration: str,
    ) -> JournalEntry:
        """Debit Accounts Payable, credit the settlement account (cash/bank)
        for a supplier payment -- the reverse of a GRN's AP credit."""
        account_code = "1000" if method == "cash" else "1010"
        return self._post_entry(
            organization_id, paid_at, "supplier_payment", supplier_payment_id, narration,
            {"2000": amount}, {account_code: amount},
        )

    def post_purchase_return(
        self, organization_id: uuid.UUID, purchase_return_id: uuid.UUID, return_date: date,
        return_number: str, taxable: float, cgst: float, sgst: float, igst: float,
    ) -> JournalEntry:
        """Reverse of a GRN posting for the returned portion: credit
        Inventory (at returned cost) and Input GST Receivable, debit
        Accounts Payable."""
        debits: dict[str, float] = {"2000": round(taxable + cgst + sgst + igst, 2)}
        credits: dict[str, float] = {"1200": round(taxable, 2)}
        if cgst:
            credits["2200"] += round(cgst, 2)
        if sgst:
            credits["2210"] += round(sgst, 2)
        if igst:
            credits["2220"] += round(igst, 2)
        return self._post_entry(
            organization_id, return_date, "purchase_return", purchase_return_id,
            f"Purchase return {return_number}", debits, credits,
        )

    def list_accounts(self, organization_id: uuid.UUID) -> list[LedgerAccount]:
        self.ledger.ensure_default_accounts(organization_id)
        stmt = (
            select(LedgerAccount)
            .where(LedgerAccount.organization_id == organization_id)
            .order_by(LedgerAccount.code)
        )
        return list(self.db.execute(stmt).scalars())

    def trial_balance(self, organization_id: uuid.UUID, as_of: date) -> TrialBalanceResponse:
        self.ledger.ensure_default_accounts(organization_id)
        stmt = (
            select(
                LedgerAccount,
                func.coalesce(func.sum(JournalLine.debit), 0),
                func.coalesce(func.sum(JournalLine.credit), 0),
            )
            .outerjoin(JournalLine, JournalLine.account_id == LedgerAccount.id)
            .outerjoin(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(LedgerAccount.organization_id == organization_id)
            .group_by(LedgerAccount.id)
        )
        if as_of is not None:
            stmt = stmt.where((JournalEntry.entry_date <= as_of) | (JournalEntry.entry_date.is_(None)))
        lines = []
        for account, debit, credit in self.db.execute(stmt).all():
            d, c = float(debit), float(credit)
            lines.append(
                TrialBalanceLine(
                    account_id=account.id, account_code=account.code, account_name=account.name,
                    account_type=account.account_type, debit_balance=d, credit_balance=c,
                )
            )
        total_debit = round(sum(line.debit_balance for line in lines), 2)
        total_credit = round(sum(line.credit_balance for line in lines), 2)
        return TrialBalanceResponse(as_of=as_of, lines=lines, total_debit=total_debit, total_credit=total_credit)

    def account_ledger(
        self, organization_id: uuid.UUID, account_id: uuid.UUID, start: date | None = None, end: date | None = None
    ) -> LedgerResponse:
        account = self.db.get(LedgerAccount, account_id)
        if account is None or account.organization_id != organization_id:
            raise NotFoundError(f"Account {account_id} not found")
        stmt_lines = (
            select(JournalLine, JournalEntry.entry_date, JournalEntry.reference_type, JournalEntry.narration)
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .where(
                JournalLine.account_id == account.id,
                JournalEntry.organization_id == organization_id,
            )
            .order_by(JournalEntry.entry_date, JournalEntry.id)
        )
        if start is not None:
            stmt_lines = stmt_lines.where(JournalEntry.entry_date >= start)
        if end is not None:
            stmt_lines = stmt_lines.where(JournalEntry.entry_date <= end)

        rows = self.db.execute(stmt_lines).all()
        opening = 0.0
        if start is not None:
            stmt_opening = select(
                func.coalesce(func.sum(JournalLine.debit - JournalLine.credit), 0)
            ).join(JournalEntry, JournalEntry.id == JournalLine.entry_id).where(
                JournalLine.account_id == account.id,
                JournalEntry.organization_id == organization_id,
                JournalEntry.entry_date < start,
            )
            opening = round(float(self.db.execute(stmt_opening).scalar_one()), 2)

        running = opening
        lines = []
        for line, entry_date, reference_type, narration in rows:
            running += float(line.debit) - float(line.credit)
            lines.append(
                AccountLedgerLine(
                    entry_id=line.entry_id, entry_date=entry_date, reference_type=reference_type,
                    narration=narration, debit=float(line.debit), credit=float(line.credit),
                    running_balance=round(running, 2),
                )
            )
        return LedgerResponse(
            account_id=account.id, account_code=account.code, account_name=account.name,
            start=start, end=end, opening_balance=opening, lines=lines, closing_balance=round(running, 2),
        )

    def post_manual_journal(self, organization_id: uuid.UUID, entry_date: date, narration: str | None, lines: list[dict]) -> JournalEntry:
        self.ledger.ensure_default_accounts(organization_id)
        entry = self.ledger.add_entry(
            JournalEntry(
                organization_id=organization_id, entry_date=entry_date, reference_type="manual",
                narration=narration,
            )
        )
        for line in lines:
            code = line["account_code"]
            account = self.ledger.get_by_code(organization_id, code)
            if account is None:
                raise ValidationError(f"Unknown account code '{code}'")
            self.ledger.add_line(
                JournalLine(entry_id=entry.id, account_id=account.id, debit=round(line.get("debit", 0), 2),
                            credit=round(line.get("credit", 0), 2))
            )
        return entry

    def post_expense(
        self, organization_id: uuid.UUID, entry_date: date, amount: float, account_code: str,
        method: str, reference: str | None, narration: str | None,
    ) -> JournalEntry:
        self.ledger.ensure_default_accounts(organization_id)
        account = self.ledger.get_by_code(organization_id, account_code)
        if account is None:
            raise ValidationError(f"Unknown account code '{account_code}'")
        if account.account_type != "expense":
            raise ValidationError(f"Account '{account_code}' ({account.name}) is not an expense account")
        settlement_code = "1000" if method == "cash" else "1010"
        return self._post_entry(
            organization_id, entry_date, "expense", uuid.uuid4(), narration or f"Expense paid via {method}",
            {account_code: amount}, {settlement_code: amount},
        )
