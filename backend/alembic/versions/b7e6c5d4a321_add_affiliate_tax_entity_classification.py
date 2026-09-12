"""add affiliate tax entity classification

Revision ID: b7e6c5d4a321
Revises: 8f4c1a2d9e07
Create Date: 2026-09-11

"""

from alembic import op
import sqlalchemy as sa

revision = "b7e6c5d4a321"
down_revision = "8f4c1a2d9e07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("affiliate_accounts", sa.Column("tax_entity_type", sa.String(), nullable=True))
    op.add_column("affiliate_accounts", sa.Column("business_name", sa.String(), nullable=True))
    op.execute("UPDATE affiliate_accounts SET tax_entity_type = 'individual' WHERE tax_entity_type IS NULL")
    op.execute("UPDATE affiliate_accounts SET tax_form_type = 'W-9' WHERE tax_status = 'us_person' AND tax_form_type IS NULL")
    op.alter_column("affiliate_accounts", "tax_entity_type", nullable=False, server_default="individual")


def downgrade() -> None:
    op.drop_column("affiliate_accounts", "business_name")
    op.drop_column("affiliate_accounts", "tax_entity_type")
