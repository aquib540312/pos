"""add zatca qr code fields

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("qr_enabled", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("sales_invoices", sa.Column("qr_code_data", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sales_invoices", "qr_code_data")
    op.drop_column("organizations", "qr_enabled")
