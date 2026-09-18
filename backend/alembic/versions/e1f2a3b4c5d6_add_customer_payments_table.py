"""add customer_payments table

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c7
Create Date: 2026-09-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

import app.models.mixins
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd1e2f3a4b5c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'customer_payments',
        sa.Column('organization_id', app.models.mixins.GUID(), nullable=False),
        sa.Column('customer_id', app.models.mixins.GUID(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('method', sa.String(length=20), nullable=False),
        sa.Column('reference', sa.String(length=120), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('id', app.models.mixins.GUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_customer_payments_customer_id'), 'customer_payments', ['customer_id'], unique=False)
    op.create_index(op.f('ix_customer_payments_organization_id'), 'customer_payments', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_customer_payments_organization_id'), table_name='customer_payments')
    op.drop_index(op.f('ix_customer_payments_customer_id'), table_name='customer_payments')
    op.drop_table('customer_payments')
