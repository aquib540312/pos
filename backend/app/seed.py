"""Seeds a demo organization so the app is usable immediately after
`docker compose up`: one branch/warehouse, an admin login, default roles,
and a starter product catalog. Run with `python -m app.seed`.
"""

from datetime import date

from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, Perm
from app.db.session import SessionLocal
from app.models.organization import Branch, Organization, Warehouse
from app.modules.auth.service import AuthService
from app.modules.catalog.service import CatalogService
from app.modules.rbac.repository import PermissionRepository
from app.modules.rbac.service import RoleService


def run() -> None:
    db = SessionLocal()
    try:
        # Safe to call on every boot (see docker-entrypoint.sh): only the
        # very first run against an empty database actually seeds anything.
        # Without this guard, re-running against an already-seeded database
        # (e.g. every redeploy) would crash on the admin email's unique
        # constraint instead of just doing nothing.
        if db.query(Organization).first() is not None:
            print("Database already seeded -- skipping.")
            return

        org = Organization(
            legal_name="Demo Retail Pvt Ltd",
            trade_name="Demo Retail",
            gstin="27AAAAA0000A1Z5",
            default_state_code="27",
        )
        db.add(org)
        db.flush()

        branch = Branch(
            organization_id=org.id, code="MAIN", name="Main Store", business_type="supermarket",
            state_code="27", gstin=org.gstin,
        )
        db.add(branch)
        db.flush()

        warehouse = Warehouse(branch_id=branch.id, code="WH1", name="Main Warehouse", is_default=True)
        db.add(warehouse)
        db.flush()

        PermissionRepository(db).ensure_seeded(Perm.ALL_PERMISSIONS)

        role_service = RoleService(db)
        roles_by_name = {}
        for role_name, perm_codes in DEFAULT_ROLE_PERMISSIONS.items():
            roles_by_name[role_name] = role_service.create_role(org.id, role_name, f"{role_name} role", perm_codes)

        admin = AuthService(db).create_user(
            organization_id=org.id,
            full_name="Admin User",
            email="admin@demo.local",
            password="ChangeMe123!",
            role_ids=[roles_by_name["admin"].id],
        )

        catalog = CatalogService(db)
        uom = catalog.create_uom(org.id, "PCS", "Pieces")
        hsn = catalog.create_hsn(
            org.id, code="1905", description="Bakery products", is_service=False,
            rate_percent=18, cess_percent=0, effective_from=date(2017, 7, 1),
        )
        catalog.create_product(
            org.id, sku="BRD-001", barcode="8901234567890", name="White Bread 400g",
            description=None, category_id=None, hsn_code_id=hsn.id, uom_id=uom.id,
            mrp=45, sale_price=40, purchase_price=30, tracks_batches=True, tracks_serials=False,
            tracks_expiry=True, reorder_level=10,
        )

        db.commit()
        print(f"Seeded organization {org.id}, branch {branch.id}, warehouse {warehouse.id}")
        print(f"Admin login: {admin.email} / ChangeMe123!")
    finally:
        db.close()


if __name__ == "__main__":
    run()
