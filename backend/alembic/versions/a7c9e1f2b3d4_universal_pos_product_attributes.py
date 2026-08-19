"""universal pos product attributes

Revision ID: a7c9e1f2b3d4
Revises: b3f5a1c7d9e4
Create Date: 2026-08-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import app.models.mixins


# revision identifiers, used by Alembic.
revision: str = 'a7c9e1f2b3d4'
down_revision: Union[str, None] = 'b3f5a1c7d9e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('brand', sa.String(length=120), nullable=True))
    op.add_column('products', sa.Column('image_path', sa.String(length=255), nullable=True))
    op.add_column('products', sa.Column('wholesale_price', sa.Numeric(precision=12, scale=2, asdecimal=False), nullable=False, server_default='0'))
    op.add_column('products', sa.Column('is_weighted', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('products', sa.Column('low_stock_notify', sa.Boolean(), nullable=False, server_default='1'))
    op.add_column('products', sa.Column('loyalty_exempt', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('products', sa.Column('prices_gst_inclusive', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('products', sa.Column('parent_product_id', app.models.mixins.GUID(), nullable=True))
    op.add_column('products', sa.Column('variant_label', sa.String(length=80), nullable=True))
    op.create_foreign_key('fk_products_parent_product_id', 'products', 'products', ['parent_product_id'], ['id'])
    op.create_table(
        'product_aliases',
        sa.Column('product_id', app.models.mixins.GUID(), nullable=False),
        sa.Column('alias', sa.String(length=120), nullable=False),
        sa.Column('organization_id', app.models.mixins.GUID(), nullable=False),
        sa.Column('id', app.models.mixins.GUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.UniqueConstraint('organization_id', 'alias', name='uq_product_alias_org_alias')
    )
    op.create_index(op.f('ix_product_aliases_product_id'), 'product_aliases', ['product_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_product_aliases_product_id'), table_name='product_aliases')
    op.drop_table('product_aliases')
    op.drop_constraint('fk_products_parent_product_id', 'products', type_='foreignkey')
    op.drop_column('products', 'variant_label')
    op.drop_column('products', 'parent_product_id')
    op.drop_column('products', 'prices_gst_inclusive')
    op.drop_column('products', 'loyalty_exempt')
    op.drop_column('products', 'low_stock_notify')
    op.drop_column('products', 'is_weighted')
    op.drop_column('products', 'wholesale_price')
    op.drop_column('products', 'image_path')
    op.drop_column('products', 'brand')