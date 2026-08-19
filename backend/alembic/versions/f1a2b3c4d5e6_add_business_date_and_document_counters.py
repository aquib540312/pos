"""add business_date to sales_invoices and document_counters table

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-08-16 10:30:00.000000

"""
from typing import Sequence, Union
from datetime import timedelta, timezone

from alembic import op
import sqlalchemy as sa

import app.models  # noqa: F401 (Base.metadata / mixins availability in newer alembic)
from app.models.mixins import GUID  # noqa: E402

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

IST = timezone(timedelta(hours=5, minutes=30))


def _backfill_business_dates() -> None:
    """backfill sales_invoices.business_date from invoice_date (Asia/Kolkata
    calendar day). invoice_date is stored UTC; SQLite returns naive values,
    Postgres returns aware ones -- treat naive as UTC (matching how the app
    always stores datetime.now(timezone.utc))."""
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, invoice_date FROM sales_invoices")).mappings()
    for row in rows:
        ts = row["invoice_date"]
        if ts is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        business_date = ts.astimezone(IST).date()
        conn.execute(
            sa.text("UPDATE sales_invoices SET business_date = :bd WHERE id = :id"),
            {"bd": business_date, "id": row["id"]},
        )


def upgrade() -> None:
    op.add_column('sales_invoices', sa.Column('business_date', sa.Date(), nullable=True))
    _backfill_business_dates()
    with op.batch_alter_table('sales_invoices') as batch_op:
        batch_op.alter_column('business_date', nullable=False)

    op.create_table(
        'document_counters',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('organization_id', GUID(), nullable=False),
        sa.Column('prefix', sa.String(length=10), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('last_number', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'prefix', 'year', name='uq_document_counter_org_prefix_year'),
    )


def downgrade() -> None:
    op.drop_table('document_counters')
    op.drop_column('sales_invoices', 'business_date')