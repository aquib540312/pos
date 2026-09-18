import sys, os, traceback
sys.path.insert(0, r'D:\pos\backend')
os.chdir(r'D:\pos\backend')

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.modules.sales.service import SalesService
from app.modules.auth.service import AuthService

db = SessionLocal()

try:
    # Find admin user
    from app.models.rbac import User
    admin = db.query(User).filter(User.email == 'admin@demo.local').first()
    if not admin:
        print("No admin user found")
        sys.exit(1)
    print(f"Admin: {admin.email}")
    
    # Find organization
    from app.models.organization import Organization
    org = db.query(Organization).first()
    if not org:
        print("No org found")
        sys.exit(1)
    print(f"Org: {org.trade_name}, id={org.id}")
    
    # Find branch
    from app.models.organization import Branch
    branch = db.query(Branch).filter(Branch.organization_id == org.id).first()
    if not branch:
        print("No branch found")
        sys.exit(1)
    print(f"Branch: {branch.name}, id={branch.id}")
    
    # Find warehouse
    from app.models.organization import Warehouse
    wh = db.query(Warehouse).filter(Warehouse.branch_id == branch.id, Warehouse.is_default == True).first()
    if not wh:
        print("No warehouse found")
        sys.exit(1)
    print(f"Warehouse: {wh.name}, id={wh.id}")
    
    # Find product with HSN
    from app.models.catalog import Product
    product = db.query(Product).filter(Product.hsn_code_id.isnot(None), Product.is_active == True).first()
    if not product:
        print("No product with HSN found")
        sys.exit(1)
    print(f"Product: {product.name}, hsn={product.hsn_code_id}")
    
    # Find customer
    from app.models.party import Customer
    customer = db.query(Customer).filter(Customer.is_credit_customer == True).first()
    if not customer:
        print("No customer found, creating one")
        from app.modules.party.service import PartyService
        service = PartyService(db)
        customer = service.create_customer(org.id, name="Test Customer", phone="9999999999", is_credit_customer=True, credit_limit=1000)
        db.commit()
    print(f"Customer: {customer.name}, id={customer.id}, credit_balance={customer.credit_balance}")
    
    # Try to create a sale
    service = SalesService(db)
    print("\nCalling create_sale...")
    invoice = service.create_sale(
        organization_id=org.id,
        branch_id=branch.id,
        warehouse_id=wh.id,
        customer_id=customer.id,
        shift_id=None,
        items=[{"product_id": product.id, "quantity": 1, "unit_price": float(product.sale_price), "discount_amount": 0}],
        payments=[{"method": "cash", "amount": float(product.sale_price)}],
        redeem_loyalty_points=0,
        is_credit_sale=False,
    )
    print(f"SUCCESS! Invoice: {invoice.invoice_number}")
except Exception as e:
    print(f"\nERROR: {type(e).__name__}: {e}")
    traceback.print_exc()
finally:
    db.close()
