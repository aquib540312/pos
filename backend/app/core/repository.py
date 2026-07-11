from __future__ import annotations

import uuid
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class SQLAlchemyRepository(Generic[ModelT]):
    """Thin CRUD base shared by module repositories.

    Business rules never live here -- this only issues queries. Modules with
    non-trivial query needs (joins, aggregates) add methods in their own
    repository subclass rather than growing this base into a query-builder.
    """

    model: type[ModelT]

    def __init__(self, db: Session):
        self.db = db

    def get(self, id_: uuid.UUID) -> ModelT | None:
        return self.db.get(self.model, id_)

    def list(self, organization_id: uuid.UUID, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        stmt = (
            select(self.model)
            .where(self.model.organization_id == organization_id)  # type: ignore[attr-defined]
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(stmt).scalars().all())

    def add(self, entity: ModelT) -> ModelT:
        self.db.add(entity)
        self.db.flush()
        return entity

    def delete(self, entity: ModelT) -> None:
        self.db.delete(entity)
        self.db.flush()
