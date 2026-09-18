"""add beef columns, waste, cutting orders, tax_mode

Revision ID: c4d5e6f7a8b9
Revises: e7f8a9b0c1d2
Create Date: 2026-09-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.models.mixins import GUID  # noqa: E402

# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'e7f8a9b0c1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_safe(table: str, column: sa.Column) -> None:
    """Add a column only if it does not already exist (idempotent)."""
    conn = op.get_bind()
    col_names = [c["name"] for c in sa.inspect(conn).get_columns(table)]
    if column.name not in col_names:
        op.add_column(table, column)


def upgrade() -> None:
    conn = op.get_bind()

    # ── products ──────────────────────────────────────────────────────
    _add_column_safe('products', sa.Column('name_arabic', sa.String(length=255), nullable=True))
    _add_column_safe('products', sa.Column('supplier_id', GUID(), nullable=True))
    _add_column_safe('products', sa.Column('wholesale_price', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'))
    _add_column_safe('products', sa.Column('restaurant_price', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'))
    _add_column_safe('products', sa.Column('vip_price', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'))
    _add_column_safe('products', sa.Column('cost_per_kg', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'))
    _add_column_safe('products', sa.Column('selling_price_per_kg', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'))
    _add_column_safe('products', sa.Column('minimum_selling_quantity', sa.Numeric(precision=12, scale=3), nullable=False, server_default='0'))
    _add_column_safe('products', sa.Column('beef_cut', sa.String(length=100), nullable=True))
    _add_column_safe('products', sa.Column('fresh_frozen', sa.String(length=20), nullable=True))
    _add_column_safe('products', sa.Column('local_imported', sa.String(length=20), nullable=True))
    _add_column_safe('products', sa.Column('country_of_origin', sa.String(length=100), nullable=True))
    _add_column_safe('products', sa.Column('storage_location', sa.String(length=100), nullable=True))

    # ── customers ─────────────────────────────────────────────────────
    _add_column_safe('customers', sa.Column('name_arabic', sa.String(length=255), nullable=True))
    _add_column_safe('customers', sa.Column('cr_number', sa.String(length=20), nullable=True))
    _add_column_safe('customers', sa.Column('customer_type', sa.String(length=30), nullable=False, server_default='walk_in'))
    _add_column_safe('customers', sa.Column('price_level', sa.String(length=20), nullable=False, server_default='retail'))
    _add_column_safe('customers', sa.Column('payment_terms_days', sa.Integer(), nullable=False, server_default='0'))
    _add_column_safe('customers', sa.Column('outstanding_balance', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'))
    _add_column_safe('customers', sa.Column('total_purchases', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'))
    _add_column_safe('customers', sa.Column('last_purchase_date', sa.DateTime(timezone=True), nullable=True))

    # ── suppliers ─────────────────────────────────────────────────────
    _add_column_safe('suppliers', sa.Column('name_arabic', sa.String(length=255), nullable=True))
    _add_column_safe('suppliers', sa.Column('cr_number', sa.String(length=20), nullable=True))

    # ── organizations ─────────────────────────────────────────────────
    _add_column_safe('organizations', sa.Column('tax_mode', sa.String(length=10), nullable=False, server_default='saudi'))

    # ── waste_entries ─────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS waste_entries (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id),
            product_id TEXT NOT NULL REFERENCES products(id),
            quantity REAL NOT NULL,
            unit_cost REAL NOT NULL,
            total_cost REAL NOT NULL,
            reason VARCHAR(50) NOT NULL,
            notes VARCHAR(500),
            recorded_by TEXT REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    op.create_index('ix_waste_entries_organization_id', 'waste_entries', ['organization_id'], if_not_exists=True)
    op.create_index('ix_waste_entries_product_id', 'waste_entries', ['product_id'], if_not_exists=True)

    # ── cutting_orders ────────────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cutting_orders (
            id TEXT PRIMARY KEY,
            organization_id TEXT NOT NULL REFERENCES organizations(id),
            source_product_id TEXT NOT NULL REFERENCES products(id),
            input_weight REAL NOT NULL,
            butcher_name VARCHAR(255),
            cutting_date TIMESTAMP,
            status VARCHAR(20) DEFAULT 'pending',
            notes VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    op.create_index('ix_cutting_orders_organization_id', 'cutting_orders', ['organization_id'], if_not_exists=True)

    # ── cutting_order_items ───────────────────────────────────────────
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cutting_order_items (
            id TEXT PRIMARY KEY,
            cutting_order_id TEXT NOT NULL REFERENCES cutting_orders(id),
            product_id TEXT NOT NULL REFERENCES products(id),
            output_weight REAL NOT NULL,
            waste_weight REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    op.create_index('ix_cutting_order_items_cutting_order_id', 'cutting_order_items', ['cutting_order_id'], if_not_exists=True)


def downgrade() -> None:
    conn = op.get_bind()

    op.drop_index('ix_cutting_order_items_cutting_order_id', table_name='cutting_order_items', if_exists=True)
    conn.execute(sa.text("DROP TABLE IF EXISTS cutting_order_items"))

    op.drop_index('ix_cutting_orders_organization_id', table_name='cutting_orders', if_exists=True)
    conn.execute(sa.text("DROP TABLE IF EXISTS cutting_orders"))

    op.drop_index('ix_waste_entries_product_id', table_name='waste_entries', if_exists=True)
    op.drop_index('ix_waste_entries_organization_id', table_name='waste_entries', if_exists=True)
    conn.execute(sa.text("DROP TABLE IF EXISTS waste_entries"))

    for table, cols in [
        ('products', ['storage_location', 'country_of_origin', 'local_imported', 'fresh_frozen', 'beef_cut',
                       'minimum_selling_quantity', 'selling_price_per_kg', 'cost_per_kg', 'vip_price',
                       'restaurant_price', 'wholesale_price', 'supplier_id', 'name_arabic']),
        ('customers', ['last_purchase_date', 'total_purchases', 'outstanding_balance', 'payment_terms_days',
                        'price_level', 'customer_type', 'cr_number', 'name_arabic']),
        ('suppliers', ['cr_number', 'name_arabic']),
        ('organizations', ['tax_mode']),
    ]:
        col_names = [c["name"] for c in sa.inspect(conn).get_columns(table)]
        for col in cols:
            if col in col_names:
                op.drop_column(table, col)
