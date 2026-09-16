"""add order_type to table_orders, allow parcel (table-less) orders

Revision ID: e7f8a9b0c1d2
Revises: d4e5f6a7b8c9
Create Date: 2026-08-20 11:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.models.mixins import GUID  # noqa: E402

# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b0c1d2'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Parcel/takeaway orders don't occupy a physical table, so table_id is
    # now optional. dine_in (the historic behaviour) stays the default. The
    # partial-unique index "one open order per table" is unaffected: parcel
    # rows carry NULL table_id, and NULLs never collide in a unique index.
    with op.batch_alter_table('table_orders') as batch_op:
        batch_op.add_column(
            sa.Column(
                'order_type',
                sa.String(length=20),
                nullable=False,
                server_default='dine_in',
            )
        )
        batch_op.alter_column('table_id', existing_type=GUID(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table('table_orders') as batch_op:
        # If any parcel rows exist their table_id is NULL and can't be
        # flipped back to NOT NULL; fail loudly rather than corrupt data.
        batch_op.alter_column('table_id', existing_type=GUID(), nullable=False)
        batch_op.drop_column('order_type')
