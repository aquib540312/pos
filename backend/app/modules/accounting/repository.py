import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.accounting import JournalEntry, JournalLine, LedgerAccount

# Control accounts every organization gets seeded with. Codes are stable
# strings the accounting service looks up by -- never hardcode a raw UUID.
DEFAULT_ACCOUNTS: list[tuple[str, str, str]] = [
    ("1000", "Cash", "asset"),
    ("1010", "Bank", "asset"),
    ("1100", "Accounts Receivable (Debtors)", "asset"),
    ("1200", "Inventory", "asset"),
    ("2000", "Accounts Payable (Creditors)", "liability"),
    ("2100", "Output CGST Payable", "liability"),
    ("2110", "Output SGST Payable", "liability"),
    ("2120", "Output IGST Payable", "liability"),
    ("2200", "Input CGST Receivable", "asset"),
    ("2210", "Input SGST Receivable", "asset"),
    ("2220", "Input IGST Receivable", "asset"),
    ("4000", "Sales Revenue", "income"),
    ("4900", "Rounding Off", "income"),
    ("5000", "Purchases", "expense"),
    ("5900", "Sales Returns", "expense"),
]


class LedgerRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_code(self, organization_id: uuid.UUID, code: str) -> LedgerAccount | None:
        stmt = select(LedgerAccount).where(LedgerAccount.organization_id == organization_id, LedgerAccount.code == code)
        return self.db.execute(stmt).scalars().first()

    def ensure_default_accounts(self, organization_id: uuid.UUID) -> None:
        existing_codes = {
            a.code for a in self.db.execute(
                select(LedgerAccount).where(LedgerAccount.organization_id == organization_id)
            ).scalars()
        }
        for code, name, account_type in DEFAULT_ACCOUNTS:
            if code not in existing_codes:
                self.db.add(
                    LedgerAccount(organization_id=organization_id, code=code, name=name, account_type=account_type, is_system=True)
                )
        self.db.flush()

    def add_entry(self, entry: JournalEntry) -> JournalEntry:
        self.db.add(entry)
        self.db.flush()
        return entry

    def add_line(self, line: JournalLine) -> JournalLine:
        self.db.add(line)
        self.db.flush()
        return line

    def list_lines_for_period(self, organization_id: uuid.UUID, account_type: str, start, end):
        stmt = (
            select(JournalLine)
            .join(JournalEntry, JournalEntry.id == JournalLine.entry_id)
            .join(LedgerAccount, LedgerAccount.id == JournalLine.account_id)
            .where(
                JournalEntry.organization_id == organization_id,
                LedgerAccount.account_type == account_type,
                JournalEntry.entry_date >= start,
                JournalEntry.entry_date <= end,
            )
        )
        return list(self.db.execute(stmt).scalars())
