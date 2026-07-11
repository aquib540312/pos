"""Import every model module so Base.metadata is fully populated for Alembic
autogenerate and for `Base.metadata.create_all` in tests."""

from app.db.base import Base  # noqa: F401
from app.models import (  # noqa: F401
    accounting,
    audit,
    billing,
    catalog,
    gst_filing,
    inventory,
    loyalty,
    organization,
    party,
    payments,
    purchasing,
    rbac,
    sales,
    sync,
)
