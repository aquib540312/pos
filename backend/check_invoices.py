import sys, os
sys.path.insert(0, r'D:\pos\backend')
os.chdir(r'D:\pos\backend')
from app.db.session import SessionLocal
from app.models.sales import DocumentCounter
from sqlalchemy import select

db = SessionLocal()

counters = db.execute(select(DocumentCounter)).scalars().all()
for c in counters:
    print(f"  id={c.id} org={c.organization_id} prefix={c.prefix} year={c.year} last={c.last_number}")

db.close()
