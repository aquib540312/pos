from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def next_document_number(db: Session, model: type, prefix: str) -> str:
    """Sequential, human-readable document number: PREFIX/YYYY/000001.

    Simplification for Phase 1: uses a row-count query, which is not
    safe under concurrent writers (two simultaneous checkouts could in
    theory race to the same number). Acceptable for a single-till/low-
    concurrency pilot; a production multi-till deployment should replace
    this with a DB sequence or a per-branch counter row locked with
    SELECT ... FOR UPDATE.
    """
    year = date.today().year
    count = db.execute(select(func.count()).select_from(model)).scalar_one()
    return f"{prefix}/{year}/{count + 1:06d}"
