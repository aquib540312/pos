import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPKMixin, org_fk


class GSTR1Filing(Base, UUIDPKMixin, TimestampMixin):
    """One row per (organization, return period) GSTR-1 filing attempt.

    `payload_json` is the exact government-schema JSON we generated and
    submitted (or would submit) -- kept verbatim so a filing can be
    re-submitted or audited without recomputing it from since-changed
    sales data. `status` tracks the GSP's lifecycle for the filing, not
    ours: generated (we built the JSON) -> submitted (sent to GSP) ->
    filed (GSP/GSTN accepted it) -> rejected.
    """

    __tablename__ = "gstr1_filings"
    __table_args__ = (UniqueConstraint("organization_id", "return_period", name="uq_gstr1_filing_org_period"),)

    organization_id: Mapped[uuid.UUID] = org_fk()
    return_period: Mapped[str] = mapped_column(String(6), nullable=False)  # MMYYYY, per GSTN convention
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="generated")
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    gsp_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
