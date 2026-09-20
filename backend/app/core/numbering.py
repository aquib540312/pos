import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.timezones import ist_today
from app.models.sales import DocumentCounter

_NUMBER_COLUMNS = ("invoice_number", "quotation_number", "return_number")


def _find_number_column(model: type) -> str:
    """Find the document number column name on the model."""
    table = model.__table__
    for name in _NUMBER_COLUMNS:
        if name in table.columns:
            return name
    for name in table.columns.keys():
        if name.endswith("_number"):
            return name
    raise ValueError(f"No document number column found for model {model.__name__}")


def _max_existing_number(db: Session, model: type, organization_id: uuid.UUID) -> int:
    """Find the highest existing document number for this organization.
    Used to seed the counter so numbering continues correctly from
    pre-existing documents.
    """
    col_name = _find_number_column(model)
    col = model.__table__.columns[col_name]
    org_col = model.__table__.columns["organization_id"]
    result = db.execute(
        select(func.max(col)).where(org_col == organization_id)
    ).scalar_one()
    if result is not None and isinstance(result, str):
        try:
            return int(result.rsplit("/", 1)[-1])
        except (ValueError, IndexError):
            pass
    return 0


def next_document_number(
    db: Session,
    model: type,
    prefix: str,
    organization_id: uuid.UUID | None = None,
    as_of: date | None = None,
) -> str:
    """Sequential, human-readable document number: PREFIX/YYYY/000001.

    Allocation is race-safe: the per-(org, prefix, year) counter row is
    locked with SELECT ... FOR UPDATE so two concurrent checkouts can never
    be handed the same number. On first use for a given counter, it is seeded
    from the highest existing number for the organization so numbering
    continues exactly where the pre-counter implementation left off.
    """
    if organization_id is None:
        raise ValueError("organization_id is required for document numbering")
    year = (as_of or ist_today()).year

    counter = db.execute(
        select(DocumentCounter)
        .where(
            DocumentCounter.organization_id == organization_id,
            DocumentCounter.prefix == prefix,
            DocumentCounter.year == year,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if counter is None:
        base = _max_existing_number(db, model, organization_id)
        savepoint = db.begin_nested()
        try:
            db.add(DocumentCounter(organization_id=organization_id, prefix=prefix, year=year, last_number=base))
            db.flush()
            savepoint.commit()
        except IntegrityError:
            savepoint.rollback()
        counter = db.execute(
            select(DocumentCounter)
            .where(
                DocumentCounter.organization_id == organization_id,
                DocumentCounter.prefix == prefix,
                DocumentCounter.year == year,
            )
            .with_for_update()
        ).scalar_one()

    counter.last_number += 1
    db.flush()
    number = f"{prefix}/{year}/{counter.last_number:06d}"

    # Safety net: if the number already exists (e.g., counter was
    # seeded incorrectly), find the next available number.
    number_col = _find_number_column(model)
    org_col = model.__table__.columns["organization_id"]
    while db.execute(
        select(func.count())
        .select_from(model)
        .where(org_col == organization_id, model.__table__.columns[number_col] == number)
    ).scalar_one() > 0:
        counter.last_number += 1
        db.flush()
        number = f"{prefix}/{year}/{counter.last_number:06d}"

    return number
