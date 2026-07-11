import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent UUID: uses Postgres UUID, stores as CHAR(36) on SQLite.

    SQLite has no native UUID type; tests run against SQLite for speed, so a
    portable type keeps model code identical across both engines instead of
    branching model definitions per test/production dialect.
    """

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(str(value)))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(str(value))


class PortableBigInteger(TypeDecorator):
    """A BigInteger primary key that also auto-increments on SQLite.

    SQLite only aliases a primary key column to its 64-bit ROWID (and
    thus auto-populates it) when the column's declared type has *exactly*
    `Integer` affinity -- a genuine `BigInteger` column doesn't qualify,
    so it would be left NULL on insert. Postgres has no such restriction
    (BIGSERIAL/IDENTITY works regardless), so only the SQLite side needs
    to downgrade to `Integer` -- SQLite's storage is 64-bit either way
    thanks to manifest typing, so nothing is actually truncated.
    """

    impl = BigInteger
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(Integer())
        return dialect.type_descriptor(BigInteger())


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def org_fk() -> MappedColumn[uuid.UUID]:
    return mapped_column(GUID(), ForeignKey("organizations.id"), nullable=False, index=True)


def branch_fk(nullable: bool = False) -> MappedColumn[uuid.UUID]:
    return mapped_column(GUID(), ForeignKey("branches.id"), nullable=nullable, index=True)
