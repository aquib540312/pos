from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.dining import DiningTable, TableOrder, TableOrderItem


class DiningTableRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, table_id: uuid.UUID) -> DiningTable | None:
        return self.db.get(DiningTable, table_id)

    def get_for_update(self, table_id: uuid.UUID) -> DiningTable | None:
        stmt = select(DiningTable).where(DiningTable.id == table_id).with_for_update()
        return self.db.execute(stmt).scalars().first()

    def add(self, table: DiningTable) -> DiningTable:
        self.db.add(table)
        self.db.flush()
        return table

    def list_by_branch(self, organization_id: uuid.UUID, branch_id: uuid.UUID) -> list[DiningTable]:
        stmt = (
            select(DiningTable)
            .where(
                DiningTable.organization_id == organization_id,
                DiningTable.branch_id == branch_id,
            )
            .order_by(DiningTable.table_number)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_open_order_for_table(self, table_id: uuid.UUID) -> TableOrder | None:
        stmt = (
            select(TableOrder)
            .where(TableOrder.table_id == table_id, TableOrder.status == "open")
            .options(
                selectinload(TableOrder.items),
                selectinload(TableOrder.table),
                selectinload(TableOrder.customer),
            )
        )
        return self.db.execute(stmt).scalars().first()


class TableOrderRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, order_id: uuid.UUID) -> TableOrder | None:
        return self.db.get(TableOrder, order_id)

    def get_for_update(self, order_id: uuid.UUID) -> TableOrder | None:
        """Fetch an order for in-place mutation, taking a row lock so two
        concurrent settle/kitchen/cancel requests cannot both read "open"
        and both proceed. SQLite ignores the FOR UPDATE but Postgres honors
        it, which is what real deployments run on."""
        stmt = (
            select(TableOrder)
            .where(TableOrder.id == order_id)
            .options(
                selectinload(TableOrder.items),
                selectinload(TableOrder.table),
                selectinload(TableOrder.customer),
            )
            .with_for_update()
        )
        return self.db.execute(stmt).scalars().first()

    def get_detailed(self, order_id: uuid.UUID) -> TableOrder | None:
        stmt = (
            select(TableOrder)
            .where(TableOrder.id == order_id)
            .options(
                selectinload(TableOrder.items),
                selectinload(TableOrder.table),
                selectinload(TableOrder.customer),
            )
        )
        return self.db.execute(stmt).scalars().first()

    def add(self, order: TableOrder) -> TableOrder:
        self.db.add(order)
        self.db.flush()
        return order

    def list_by_branch(
        self, organization_id: uuid.UUID, branch_id: uuid.UUID, status: str | None = None
    ) -> list[TableOrder]:
        stmt = (
            select(TableOrder)
            .where(TableOrder.organization_id == organization_id, TableOrder.branch_id == branch_id)
            .options(
                selectinload(TableOrder.items),
                selectinload(TableOrder.table),
                selectinload(TableOrder.customer),
            )
            .order_by(TableOrder.opened_at.desc())
        )
        if status:
            stmt = stmt.where(TableOrder.status == status)
        return list(self.db.execute(stmt).scalars().all())

    def add_item(self, item: TableOrderItem) -> TableOrderItem:
        self.db.add(item)
        self.db.flush()
        return item

    def get_item(self, item_id: uuid.UUID) -> TableOrderItem | None:
        return self.db.get(TableOrderItem, item_id)
