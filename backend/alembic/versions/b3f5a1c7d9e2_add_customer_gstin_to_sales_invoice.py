"""add customer_gstin to sales invoice

Revision ID: b3f5a1c7d9e2
Revises: 9964fe50d368
Create Date: 2026-07-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f5a1c7d9e2'
down_revision: Union[str, None] = '9964fe50d368'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sales_invoices', sa.Column('customer_gstin', sa.String(length=15), nullable=True))


def downgrade() -> None:
    op.drop_column('sales_invoices', 'customer_gstin')
