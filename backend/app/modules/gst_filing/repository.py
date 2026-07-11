import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.gst_filing import GSTR1Filing


class GSTR1FilingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_period(self, organization_id: uuid.UUID, return_period: str) -> GSTR1Filing | None:
        stmt = select(GSTR1Filing).where(
            GSTR1Filing.organization_id == organization_id, GSTR1Filing.return_period == return_period
        )
        return self.db.execute(stmt).scalars().first()

    def add(self, filing: GSTR1Filing) -> GSTR1Filing:
        self.db.add(filing)
        self.db.flush()
        return filing
