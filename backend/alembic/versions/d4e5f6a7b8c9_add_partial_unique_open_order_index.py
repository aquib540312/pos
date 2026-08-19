"""add partial unique index for one open order per table

Revision ID: d4e5f6a7b8c9
Revises: c8d9e0f1a2b3
Create Date: 2026-08-17 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c8d9e0f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Concurrency guard: only one open order may exist per table. Existing
    # deployments which somehow carry duplicate open orders for the same
    # table (only possible via a race before this migration) must be
    # reconciled before applying; SQLite/Postgres will surface the conflict
    # as an index build error, which is the intended loud failure.
    op.create_index(
        "uq_table_orders_one_open_per_table",
        "table_orders",
        ["table_id"],
        unique=True,
        sqlite_where="status = 'open'",
        postgresql_where="status = 'open'",
    )


def downgrade() -> None:
    op.drop_index("uq_table_orders_one_open_per_table", table_name="table_orders")