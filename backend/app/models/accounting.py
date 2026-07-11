import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import GUID, TimestampMixin, UUIDPKMixin, org_fk

# Ledger account types drive P&L vs Balance Sheet classification when
# reports are generated (asset/liability/equity -> balance sheet;
# income/expense -> profit & loss).
ACCOUNT_TYPES = ("asset", "liability", "equity", "income", "expense")


class LedgerAccount(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "ledger_accounts"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_ledger_account_org_code"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_system: Mapped[bool] = mapped_column(default=False)  # seeded control accounts, not user-deletable


class JournalEntry(Base, UUIDPKMixin, TimestampMixin):
    """A balanced double-entry posting. Every sale/purchase/payment posts one
    of these automatically (see accounting/service.py); manual journal
    entries are also supported for adjustments. Immutable once created --
    reversals are posted as new entries."""

    __tablename__ = "journal_entries"

    organization_id: Mapped[uuid.UUID] = org_fk()
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    reference_type: Mapped[str] = mapped_column(String(30), nullable=False)  # sales_invoice|purchase|payment|manual
    reference_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    narration: Mapped[str | None] = mapped_column(String(255))

    lines: Mapped[list["JournalLine"]] = relationship(back_populates="entry")


class JournalLine(Base, UUIDPKMixin):
    __tablename__ = "journal_lines"

    entry_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("journal_entries.id"), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("ledger_accounts.id"), nullable=False, index=True)
    debit: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)
    credit: Mapped[float] = mapped_column(Numeric(12, 2, asdecimal=False), nullable=False, default=0)

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
    account: Mapped["LedgerAccount"] = relationship()
