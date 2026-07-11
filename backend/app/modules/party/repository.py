from __future__ import annotations

import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.party import Customer, Supplier


class CustomerRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, organization_id: uuid.UUID, search: str | None = None) -> list[Customer]:
        stmt = select(Customer).where(Customer.organization_id == organization_id, Customer.is_active.is_(True))
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(Customer.name.ilike(like), Customer.phone.ilike(like)))
        return list(self.db.execute(stmt).scalars())

    def get(self, customer_id: uuid.UUID) -> Customer | None:
        return self.db.get(Customer, customer_id)

    def add(self, customer: Customer) -> Customer:
        self.db.add(customer)
        self.db.flush()
        return customer


class SupplierRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, organization_id: uuid.UUID) -> list[Supplier]:
        return list(
            self.db.execute(
                select(Supplier).where(Supplier.organization_id == organization_id, Supplier.is_active.is_(True))
            ).scalars()
        )

    def get(self, supplier_id: uuid.UUID) -> Supplier | None:
        return self.db.get(Supplier, supplier_id)

    def add(self, supplier: Supplier) -> Supplier:
        self.db.add(supplier)
        self.db.flush()
        return supplier
