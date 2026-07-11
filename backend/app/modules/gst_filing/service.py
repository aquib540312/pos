import calendar
import json
import uuid
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.models.gst_filing import GSTR1Filing
from app.modules.gst_filing.adapters import GSPAdapter, get_gsp_adapter
from app.modules.gst_filing.repository import GSTR1FilingRepository
from app.modules.gst_filing.schema_builder import build_gstr1_json
from app.modules.reports.service import ReportService


def parse_return_period(return_period: str) -> tuple[date, date]:
    """GSTN's return period convention is MMYYYY, e.g. "072026" for July
    2026 -- not ISO, so it needs explicit parsing rather than date.fromisoformat."""
    if len(return_period) != 6 or not return_period.isdigit():
        raise ValidationError("return_period must be in MMYYYY format, e.g. '072026'")
    month, year = int(return_period[:2]), int(return_period[2:])
    if not 1 <= month <= 12:
        raise ValidationError(f"Invalid month in return_period: {return_period}")
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


class GSTFilingService:
    def __init__(self, db: Session, settings: Settings | None = None, adapter: GSPAdapter | None = None):
        self.db = db
        self.filings = GSTR1FilingRepository(db)
        self.reports = ReportService(db)
        self.settings = settings or get_settings()
        self.adapter: GSPAdapter = adapter or get_gsp_adapter(self.settings)

    def generate_gstr1(self, organization_id: uuid.UUID, return_period: str, gstin: str) -> GSTR1Filing:
        start, end = parse_return_period(return_period)
        hsn_lines = self.reports.gstr1_summary(organization_id, start, end)
        b2cs_lines = self.reports.gstr1_b2cs_summary(organization_id, start, end)
        gross_turnover = self.reports.gross_turnover(organization_id, start, end)
        payload = build_gstr1_json(gstin, return_period, gross_turnover, hsn_lines, b2cs_lines)
        payload_json = json.dumps(payload)

        existing = self.filings.get_by_period(organization_id, return_period)
        if existing is not None:
            if existing.status in ("submitted", "filed"):
                raise ValidationError(
                    f"GSTR-1 for {return_period} was already {existing.status}; cannot regenerate"
                )
            existing.payload_json = payload_json
            existing.period_start = start
            existing.period_end = end
            self.db.flush()
            return existing

        filing = GSTR1Filing(
            organization_id=organization_id,
            return_period=return_period,
            period_start=start,
            period_end=end,
            status="generated",
            payload_json=payload_json,
        )
        return self.filings.add(filing)

    def submit_gstr1(self, organization_id: uuid.UUID, return_period: str, gstin: str) -> GSTR1Filing:
        filing = self.filings.get_by_period(organization_id, return_period)
        if filing is None:
            raise NotFoundError(f"No generated GSTR-1 filing for {return_period}; generate it first")
        if filing.status in ("submitted", "filed"):
            raise ValidationError(f"GSTR-1 for {return_period} was already {filing.status}")

        try:
            result = self.adapter.submit_gstr1(gstin, return_period, json.loads(filing.payload_json))
        except Exception as exc:  # noqa: BLE001 - any GSP failure (network/auth/GSTN downtime) is a filing rejection
            filing.status = "rejected"
            filing.error_message = str(exc)
            self.db.flush()
            raise ValidationError(f"GSP submission failed: {exc}") from exc

        filing.gsp_reference = result.gsp_reference
        filing.status = result.status
        filing.submitted_at = datetime.now(timezone.utc)
        if result.status == "filed":
            filing.filed_at = datetime.now(timezone.utc)
        self.db.flush()
        return filing

    def check_status(self, organization_id: uuid.UUID, return_period: str) -> GSTR1Filing:
        filing = self.filings.get_by_period(organization_id, return_period)
        if filing is None:
            raise NotFoundError(f"No filing found for period {return_period}")
        if filing.gsp_reference:
            status = self.adapter.get_status(filing.gsp_reference)
            filing.status = status
            if status == "filed" and filing.filed_at is None:
                filing.filed_at = datetime.now(timezone.utc)
            self.db.flush()
        return filing
