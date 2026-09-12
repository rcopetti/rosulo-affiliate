"""add postal_code to affiliate_accounts

Revision ID: 8f4c1a2d9e07
Revises: 2a35d2bb1e8b
Create Date: 2026-09-11

"""

from alembic import op
import sqlalchemy as sa


revision = "8f4c1a2d9e07"
down_revision = "2a35d2bb1e8b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("affiliate_accounts", sa.Column("postal_code", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("affiliate_accounts", "postal_code")
