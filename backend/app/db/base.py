from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models in every module.

    Kept in one place (rather than per-module bases) because the schema is
    highly relational -- FKs cross module boundaries constantly (a sales
    invoice line references a product, a batch, a tax rate). Splitting the
    metadata per module would only complicate Alembic autogenerate for no
    real isolation benefit at this stage.
    """
