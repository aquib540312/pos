from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models.catalog import Category, HSNCode, Product, TaxRate, UnitOfMeasure


class CategoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, organization_id: uuid.UUID) -> list[Category]:
        return list(self.db.execute(select(Category).where(Category.organization_id == organization_id)).scalars())

    def add(self, category: Category) -> Category:
        self.db.add(category)
        self.db.flush()
        return category


class UOMRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, organization_id: uuid.UUID) -> list[UnitOfMeasure]:
        return list(
            self.db.execute(select(UnitOfMeasure).where(UnitOfMeasure.organization_id == organization_id)).scalars()
        )

    def add(self, uom: UnitOfMeasure) -> UnitOfMeasure:
        self.db.add(uom)
        self.db.flush()
        return uom


class HSNRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, organization_id: uuid.UUID) -> list[HSNCode]:
        return list(self.db.execute(select(HSNCode).where(HSNCode.organization_id == organization_id)).scalars())

    def get(self, hsn_id: uuid.UUID) -> HSNCode | None:
        return self.db.get(HSNCode, hsn_id)

    def add(self, hsn: HSNCode) -> HSNCode:
        self.db.add(hsn)
        self.db.flush()
        return hsn

    def add_tax_rate(self, tax_rate: TaxRate) -> TaxRate:
        self.db.add(tax_rate)
        self.db.flush()
        return tax_rate

    def get_effective_tax_rate(self, hsn_code_id: uuid.UUID, as_of: date) -> TaxRate | None:
        """The GST slab in force for this HSN/SAC on the given date. Rates
        are versioned (effective_from/effective_to) so historical invoices
        keep reporting the rate that applied when they were posted, even
        after a government rate change."""
        stmt = select(TaxRate).where(
            TaxRate.hsn_code_id == hsn_code_id,
            TaxRate.effective_from <= as_of,
            or_(TaxRate.effective_to.is_(None), TaxRate.effective_to >= as_of),
        )
        return self.db.execute(stmt).scalars().first()


class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, organization_id: uuid.UUID, *, search: str | None = None, limit: int = 100) -> list[Product]:
        stmt = select(Product).where(Product.organization_id == organization_id, Product.is_active.is_(True))
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(Product.name.ilike(like), Product.sku.ilike(like), Product.barcode.ilike(like)))
        return list(self.db.execute(stmt.limit(limit)).scalars())

    def get(self, product_id: uuid.UUID) -> Product | None:
        return self.db.get(Product, product_id)

    def get_by_barcode(self, organization_id: uuid.UUID, barcode: str) -> Product | None:
        stmt = select(Product).where(
            and_(Product.organization_id == organization_id, Product.barcode == barcode, Product.is_active.is_(True))
        )
        return self.db.execute(stmt).scalars().first()

    def get_by_sku(self, organization_id: uuid.UUID, sku: str) -> Product | None:
        stmt = select(Product).where(Product.organization_id == organization_id, Product.sku == sku)
        return self.db.execute(stmt).scalars().first()

    def add(self, product: Product) -> Product:
        self.db.add(product)
        self.db.flush()
        return product
