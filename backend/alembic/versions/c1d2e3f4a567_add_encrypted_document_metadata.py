"""add encrypted document metadata

Revision ID: c1d2e3f4a567
Revises: b7e6c5d4a321
Create Date: 2026-09-11

"""

from alembic import op
import sqlalchemy as sa

revision = "c1d2e3f4a567"
down_revision = "b7e6c5d4a321"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("affiliate_documents", sa.Column("content_type", sa.String(), nullable=True))
    op.add_column("affiliate_documents", sa.Column("file_size", sa.Integer(), nullable=True))
    op.execute("UPDATE affiliate_documents SET content_type = 'application/octet-stream' WHERE content_type IS NULL")
    op.execute("UPDATE affiliate_documents SET file_size = 0 WHERE file_size IS NULL")
    op.alter_column("affiliate_documents", "content_type", nullable=False, server_default="application/octet-stream")
    op.alter_column("affiliate_documents", "file_size", nullable=False, server_default="0")


def downgrade() -> None:
    op.drop_column("affiliate_documents", "file_size")
    op.drop_column("affiliate_documents", "content_type")
