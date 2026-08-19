"""add organization branding columns (logo, phone, address, footer note)

Revision ID: e5f6a7b8c9d0
Revises: d1e2f3a4b5c6
Create Date: 2026-08-16 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('logo_path', sa.String(length=255), nullable=True))
    op.add_column('organizations', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('organizations', sa.Column('address', sa.String(length=500), nullable=True))
    op.add_column('organizations', sa.Column('footer_note', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('organizations', 'footer_note')
    op.drop_column('organizations', 'address')
    op.drop_column('organizations', 'phone')
    op.drop_column('organizations', 'logo_path')