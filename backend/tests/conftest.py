import os
from datetime import date

os.environ.setdefault("POS_DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("POS_SECRET_KEY", "test-secret-key")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401 (populate Base.metadata)
from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, Perm  # noqa: E402
from app.core.security import create_access_token  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.organization import Branch, Organization, Warehouse  # noqa: E402
from app.modules.auth.service import AuthService  # noqa: E402
from app.modules.catalog.service import CatalogService  # noqa: E402
from app.modules.rbac.repository import PermissionRepository  # noqa: E402
from app.modules.rbac.service import RoleService  # noqa: E402


@pytest.fixture()
def db_session():
    """A fresh in-memory SQLite database per test -- fast enough (schema
    creation is milliseconds) that isolating at the whole-database level is
    simpler and safer than nested-transaction tricks, given the app code
    calls session.commit() directly inside request handlers."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded_org(db_session):
    """Mirrors app/seed.py: one org/branch/warehouse, all default roles,
    an admin user, and a starter product with GST configured -- used by
    every integration test so they don't each hand-roll fixture data."""
    org = Organization(legal_name="Test Retail Pvt Ltd", trade_name="Test Retail", default_state_code="27")
    db_session.add(org)
    db_session.flush()

    branch = Branch(organization_id=org.id, code="MAIN", name="Main Store", business_type="grocery", state_code="27")
    db_session.add(branch)
    db_session.flush()

    warehouse = Warehouse(branch_id=branch.id, code="WH1", name="Main Warehouse", is_default=True)
    db_session.add(warehouse)
    db_session.flush()

    PermissionRepository(db_session).ensure_seeded(Perm.ALL_PERMISSIONS)
    role_service = RoleService(db_session)
    admin_role = None
    for role_name, perm_codes in DEFAULT_ROLE_PERMISSIONS.items():
        role = role_service.create_role(org.id, role_name, f"{role_name} role", perm_codes)
        if role_name == "admin":
            admin_role = role

    admin = AuthService(db_session).create_user(
        organization_id=org.id, full_name="Admin", email="admin@test.local", password="TestPass123!",
        role_ids=[admin_role.id],
    )

    catalog = CatalogService(db_session)
    uom = catalog.create_uom(org.id, "PCS", "Pieces")
    hsn = catalog.create_hsn(
        org.id, code="1905", description="Bakery", is_service=False, rate_percent=18, cess_percent=0,
        effective_from=date(2017, 7, 1),
    )
    product = catalog.create_product(
        org.id, sku="BRD-001", barcode="8901234567890", name="White Bread 400g", description=None,
        category_id=None, hsn_code_id=hsn.id, uom_id=uom.id, mrp=45, sale_price=40, purchase_price=30,
        tracks_batches=True, tracks_serials=False, tracks_expiry=True, reorder_level=10,
    )
    db_session.commit()

    token = create_access_token(subject=str(admin.id), extra_claims={"org": str(org.id)})

    return {
        "organization": org,
        "branch": branch,
        "warehouse": warehouse,
        "admin": admin,
        "product": product,
        "hsn": hsn,
        "uom": uom,
        "auth_headers": {"Authorization": f"Bearer {token}"},
    }
