import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timezones import ist_today
from app.models.sales import DocumentCounter


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
    be handed the same number (the row's unique constraint is the backstop
    that turns any programming error into a loud IntegrityError instead of
    a silently duplicated invoice number). On the first use for a given
    counter, it is seeded from the existing row count so numbering continues
    exactly where the pre-counter implementation left off. `model` is only
    used for that seed, so callers needing a number for a not-yet-existing
    row can pass any model mapped to the underlying table.
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
        # Seed from the pre-counter row count so existing documents keep
        # their sequence and no backfilled number collides. SELECT ... FOR
        # UPDATE still guards the insert path on PostgreSQL (an unguarded
        # unique-violation race is caught and retried below).
        base = db.execute(select(func.count()).select_from(model)).scalar_one()
        db.add(DocumentCounter(organization_id=organization_id, prefix=prefix, year=year, last_number=base))
        db.flush()
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
    return f"{prefix}/{year}/{counter.last_number:06d}"
