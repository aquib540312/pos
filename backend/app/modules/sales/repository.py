from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.sales import Quotation, QuotationItem, SalesInvoice, SalesInvoiceItem, SalesReturn


class SalesInvoiceRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, invoice: SalesInvoice) -> SalesInvoice:
        self.db.add(invoice)
        self.db.flush()
        return invoice

    def add_item(self, item: SalesInvoiceItem) -> SalesInvoiceItem:
        self.db.add(item)
        self.db.flush()
        return item

    def get(self, invoice_id: uuid.UUID) -> SalesInvoice | None:
        stmt = (
            select(SalesInvoice)
            .where(SalesInvoice.id == invoice_id)
            .options(selectinload(SalesInvoice.items), selectinload(SalesInvoice.payments))
        )
        return self.db.execute(stmt).scalars().first()

    def get_item(self, item_id: uuid.UUID) -> SalesInvoiceItem | None:
        return self.db.get(SalesInvoiceItem, item_id)

    def list(self, organization_id: uuid.UUID, branch_id: uuid.UUID | None = None) -> list[SalesInvoice]:
        stmt = (
            select(SalesInvoice)
            .where(SalesInvoice.organization_id == organization_id)
            .options(selectinload(SalesInvoice.items), selectinload(SalesInvoice.payments))
        )
        if branch_id:
            stmt = stmt.where(SalesInvoice.branch_id == branch_id)
        return list(self.db.execute(stmt).scalars())


class SalesReturnRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, sales_return: SalesReturn) -> SalesReturn:
        self.db.add(sales_return)
        self.db.flush()
        return sales_return

    def get(self, return_id: uuid.UUID) -> SalesReturn | None:
        stmt = select(SalesReturn).where(SalesReturn.id == return_id).options(selectinload(SalesReturn.items))
        return self.db.execute(stmt).scalars().first()

    def list(self, organization_id: uuid.UUID) -> list[SalesReturn]:
        stmt = (
            select(SalesReturn)
            .where(SalesReturn.organization_id == organization_id)
            .options(selectinload(SalesReturn.items))
            .order_by(SalesReturn.return_date.desc())
        )
        return list(self.db.execute(stmt).scalars())


class QuotationRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, quotation: Quotation) -> Quotation:
        self.db.add(quotation)
        self.db.flush()
        return quotation

    def add_item(self, item: QuotationItem) -> QuotationItem:
        self.db.add(item)
        self.db.flush()
        return item

    def get(self, quotation_id: uuid.UUID) -> Quotation | None:
        stmt = select(Quotation).where(Quotation.id == quotation_id).options(selectinload(Quotation.items))
        return self.db.execute(stmt).scalars().first()

    def list(self, organization_id: uuid.UUID) -> list[Quotation]:
        stmt = (
            select(Quotation)
            .where(Quotation.organization_id == organization_id)
            .options(selectinload(Quotation.items))
            .order_by(Quotation.quotation_date.desc())
        )
        return list(self.db.execute(stmt).scalars())
