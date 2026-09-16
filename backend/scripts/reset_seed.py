"""Fresh full reset + restaurant seed for D:/pos demo.

Run from backend dir:  python scripts/reset_seed.py
Deletes nothing itself -- assumes an empty/fresh DB (schema created via
Base.metadata.create_all). Builds a fresh restaurant company and a full
menu, tables, and per-product images.
"""
import os
from datetime import date

from app.db.session import SessionLocal, engine
from app.models import Base  # noqa: F401  (imports all models, populates Base.metadata)
from app.modules.auth.service import AuthService
from app.modules.catalog.service import CatalogService
from app.modules.rbac.repository import PermissionRepository
from app.core.permissions import Perm
from app.models.organization import Branch, Warehouse
from app.modules.dining.service import DiningService
from app.models.subscriptions import Plan

from PIL import Image, ImageDraw, ImageFont, ImageFilter

UPLOADS = "D:/pos/backend/uploads"
os.makedirs(UPLOADS, exist_ok=True)

CAT_GRAD = {
    "starters": ((120, 60, 20), (210, 140, 70)),
    "main": ((30, 90, 60), (120, 200, 160)),
    "breads": ((120, 75, 35), (238, 209, 160)),
    "beverages": ((20, 70, 130), (120, 180, 230)),
    "desserts": ((110, 30, 70), (230, 120, 170)),
}

MENU = [
    ("starters", [
        ("ST-001", "Paneer Tikka", 280, 320, "🧀"),
        ("ST-002", "Chicken Seekh Kebab", 320, 360, "🍢"),
        ("ST-003", "Veg Spring Roll", 180, 210, "🥟"),
        ("ST-004", "Chilli Potato", 200, 230, "🥔"),
    ]),
    ("main", [
        ("MN-001", "Butter Chicken", 380, 420, "🍗"),
        ("MN-002", "Paneer Butter Masala", 320, 360, "🧈"),
        ("MN-003", "Dal Tadka", 220, 250, "🍲"),
        ("MN-004", "Veg Biryani", 260, 300, "🍚"),
        ("MN-005", "Chicken Curry", 340, 380, "🍛"),
    ]),
    ("breads", [
        ("BR-001", "Butter Naan", 40, 45, "🫓"),
        ("BR-002", "Tandoori Roti", 30, 35, "🍞"),
        ("BR-003", "Garlic Naan", 50, 55, "🧄"),
        ("BR-004", "Laccha Paratha", 60, 70, "🥯"),
    ]),
    ("beverages", [
        ("BV-001", "Sweet Lassi", 90, 100, "🥛"),
        ("BV-002", "Masala Chai", 60, 70, "🍵"),
        ("BV-003", "Cold Coffee", 120, 140, "☕"),
        ("BV-004", "Soft Drink (Can)", 60, 70, "🥤"),
    ]),
    ("desserts", [
        ("DS-001", "Gulab Jamun", 90, 100, "🍮"),
        ("DS-002", "Ice Cream (2 scoops)", 110, 130, "🍨"),
        ("DS-003", "Rasgulla", 80, 90, "🍬"),
    ]),
]


def make_image(name, emoji, c1, c2):
    W, H = 640, 480
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / max(H - 1, 1)
        r = int(c1[0] + (c2[0] - c1[0]) * t)
        g = int(c1[1] + (c2[1] - c1[1]) * t)
        b = int(c1[2] + (c2[2] - c1[2]) * t)
        d.line([(0, y), (W, y)], fill=(r, g, b))
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    cx, cy = W // 2, H // 2 - 12
    for rr, alpha in [(170, 26), (120, 34), (80, 42)]:
        od.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(255, 255, 255, alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    efont = ImageFont.truetype("C:/Windows/Fonts/seguiemj.ttf", 150)
    d = ImageDraw.Draw(img)
    d.text((cx, cy), emoji, font=efont, anchor="mm", stroke_width=6, stroke_fill=(0, 0, 0, 80))
    tfont = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 44)
    d.text((W // 2, H - 52), name, font=tfont, anchor="mm", fill=(255, 255, 255),
           stroke_width=2, stroke_fill=(0, 0, 0, 140))
    return img


print("Creating schema...")
Base.metadata.create_all(engine)

# Seed subscription plans (normally done by migration; create_all has no data)
from app.db.session import SessionLocal as _S
_pdb = _S()
try:
    if _pdb.query(Plan).count() == 0:
        for code, name, price, branches, users in [
            ("starter", "Starter", 0, 1, 3),
            ("growth", "Growth", 999, 3, 15),
            ("enterprise", "Enterprise", 2999, None, None),
        ]:
            _pdb.add(Plan(code=code, name=name, price_monthly=price,
                          max_branches=branches, max_users=users, is_active=True))
        _pdb.commit()
        print("Seeded subscription plans")
finally:
    _pdb.close()

db = SessionLocal()
try:
    auth = AuthService(db)
    admin_user, token = auth.signup(
        legal_name="Spice Garden Restaurant LLP",
        trade_name="Spice Garden",
        default_state_code="27",
        gstin="27ABCDE1234F1Z5",
        branch_code="MG01",
        branch_name="MG Road",
        admin_full_name="Restaurant Admin",
        admin_email="admin@demo.local",
        admin_password="ChangeMe123!",
        admin_phone=None,
        plan_code="starter",
    )
    org_id = admin_user.organization_id
    print(f"Company created: org={org_id} admin={admin_user.email}")
    PermissionRepository(db).ensure_seeded(Perm.ALL_PERMISSIONS)

    branch = db.query(Branch).filter(Branch.organization_id == org_id).first()
    branch_id = branch.id
    warehouse = db.query(Warehouse).filter(
        Warehouse.branch_id == branch_id, Warehouse.is_default == True
    ).first()
    if warehouse is None:
        warehouse = db.query(Warehouse).filter(Warehouse.branch_id == branch_id).first()

    catalog = CatalogService(db)
    pcs = catalog.create_uom(org_id, "PCS", "Pieces")
    food_hsn = catalog.create_hsn(org_id, "9963", "Restaurant & catering services", False, 5, 0, date(2017, 7, 1))
    bev_hsn = catalog.create_hsn(org_id, "2202", "Aerated soft drinks", False, 18, 0, date(2017, 7, 1))

    cats = {}
    for cat_key, items in MENU:
        cats[cat_key] = catalog.create_category(org_id, cat_key.capitalize(), None)

    hsn_by_cat = {
        "beverages": bev_hsn,
        "starters": food_hsn,
        "main": food_hsn,
        "breads": food_hsn,
        "desserts": food_hsn,
    }

    count = 0
    for cat_key, items in MENU:
        grad = CAT_GRAD[cat_key]
        for sku, name, mrp, sale, emoji in items:
            p = catalog.create_product(
                org_id,
                sku=sku,
                name=name,
                category_id=cats[cat_key].id,
                hsn_code_id=hsn_by_cat[cat_key].id,
                uom_id=pcs.id,
                mrp=mrp,
                sale_price=sale,
                purchase_price=round(sale * 0.6, 2),
                tracks_batches=False,
                tracks_serials=False,
                tracks_expiry=False,
                warehouse_id=warehouse.id,
                initial_stock_qty=100,
            )
            img = make_image(name, emoji, grad[0], grad[1])
            fname = f"{p.id}.png"
            img.save(os.path.join(UPLOADS, fname), "PNG")
            p.image_path = fname
            db.add(p)
            count += 1
    print(f"Created {count} products with images")

    ds = DiningService(db)
    for i in range(1, 13):
        ds.create_table(org_id, branch_id, f"T{i}", f"Table {i}", 4)
    print("Created 12 tables (T1..T12)")

    db.commit()
    print("DONE. Login: admin@demo.local / ChangeMe123!")
finally:
    db.close()
