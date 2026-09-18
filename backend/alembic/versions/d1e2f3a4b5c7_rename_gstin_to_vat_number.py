"""rename gstin to vat_number in customers table

Revision ID: d1e2f3a4b5c7
Revises: b3f5a1c7d9e3
Create Date: 2026-09-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c7'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('customers') as batch_op:
        batch_op.alter_column('gstin', new_column_name='vat_number')


def downgrade() -> None:
    with op.batch_alter_table('customers') as batch_op:
        batch_op.alter_column('vat_number', new_column_name='gstin')
