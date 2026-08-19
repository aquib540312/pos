"""add discount to purchasing

Revision ID: d1e2f3a4b5c6
Revises: a7c9e1f2b3d4
Create Date: 2026-08-15 10:44:47.525372

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models.mixins


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'a7c9e1f2b3d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'purchase_order_items',
        sa.Column(
            'discount_amount', sa.Numeric(precision=12, scale=2, asdecimal=False),
            nullable=False, server_default='0',
        ),
    )
    op.add_column(
        'goods_receipt_items',
        sa.Column(
            'discount_amount', sa.Numeric(precision=12, scale=2, asdecimal=False),
            nullable=False, server_default='0',
        ),
    )


def downgrade() -> None:
    op.drop_column('goods_receipt_items', 'discount_amount')
    op.drop_column('purchase_order_items', 'discount_amount')
