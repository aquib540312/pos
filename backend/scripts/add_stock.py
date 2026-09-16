"""Add opening stock to all products in the default warehouse (non-destructive)."""
import uuid
from app.db.session import SessionLocal
from app.models.organization import Branch, Warehouse
from app.models.catalog import Product
from app.modules.inventory.service import InventoryService

db = SessionLocal()
try:
    org_id = db.query(Product).first().organization_id
    branch = db.query(Branch).filter(Branch.organization_id == org_id).first()
    wh = db.query(Warehouse).filter(Warehouse.branch_id == branch.id, Warehouse.is_default == True).first()
    if wh is None:
        wh = db.query(Warehouse).filter(Warehouse.branch_id == branch.id).first()
    print(f"org={org_id} branch={branch.id} warehouse={wh.id}")

    svc = InventoryService(db)
    n = 0
    for p in db.query(Product).filter(Product.organization_id == org_id).all():
        svc.receive(
            org_id, wh.id, p.id, None, 100.0,
            "adjustment_in", "opening_stock", uuid.uuid4(), "Opening stock",
        )
        n += 1
    db.commit()
    print(f"Added 100 units opening stock to {n} products")
finally:
    db.close()
