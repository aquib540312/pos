"""add dining tables + table orders + kitchen tickets (KOT)

Revision ID: c8d9e0f1a2b3
Revises: f1a2b3c4d5e6
Create Date: 2026-08-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models.mixins import GUID  # noqa: E402

# revision identifiers, used by Alembic.
revision: str = 'c8d9e0f1a2b3'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dining_tables',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('organization_id', GUID(), nullable=False),
        sa.Column('branch_id', GUID(), nullable=False),
        sa.Column('table_number', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=True),
        sa.Column('capacity', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'branch_id', 'table_number', name='uq_dining_table_org_branch_number'),
    )
    op.create_index('ix_dining_tables_organization_id', 'dining_tables', ['organization_id'])
    op.create_index('ix_dining_tables_branch_id', 'dining_tables', ['branch_id'])

    op.create_table(
        'table_orders',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('organization_id', GUID(), nullable=False),
        sa.Column('branch_id', GUID(), nullable=False),
        sa.Column('table_id', GUID(), nullable=False),
        sa.Column('customer_id', GUID(), nullable=True),
        sa.Column('shift_id', GUID(), nullable=True),
        sa.Column('sales_invoice_id', GUID(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('kot_counter', sa.Integer(), nullable=False),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['branch_id'], ['branches.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['sales_invoice_id'], ['sales_invoices.id']),
        sa.ForeignKeyConstraint(['shift_id'], ['shifts.id']),
        sa.ForeignKeyConstraint(['table_id'], ['dining_tables.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_table_orders_organization_id', 'table_orders', ['organization_id'])
    op.create_index('ix_table_orders_branch_id', 'table_orders', ['branch_id'])
    op.create_index('ix_table_orders_table_id', 'table_orders', ['table_id'])

    op.create_table(
        'table_order_items',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('order_id', GUID(), nullable=False),
        sa.Column('product_id', GUID(), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column('unit_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('discount_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('kot_number', sa.String(length=20), nullable=True),
        sa.Column('sent_to_kitchen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['table_orders.id']),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_table_order_items_order_id', 'table_order_items', ['order_id'])


def downgrade() -> None:
    op.drop_index('ix_table_order_items_order_id', table_name='table_order_items')
    op.drop_table('table_order_items')
    op.drop_index('ix_table_orders_table_id', table_name='table_orders')
    op.drop_index('ix_table_orders_branch_id', table_name='table_orders')
    op.drop_index('ix_table_orders_organization_id', table_name='table_orders')
    op.drop_table('table_orders')
    op.drop_index('ix_dining_tables_branch_id', table_name='dining_tables')
    op.drop_index('ix_dining_tables_organization_id', table_name='dining_tables')
    op.drop_table('dining_tables')