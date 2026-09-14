"""add password reset codes

Revision ID: f7a8b9c0d123
Revises: c1d2e3f4a567
Create Date: 2026-09-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7a8b9c0d123'
down_revision: Union[str, None] = 'c1d2e3f4a567'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'password_reset_codes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('user_type', sa.String(), nullable=False),
        sa.Column('code_hash', sa.String(), nullable=True),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reset_token_hash', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', 'user_type'),
    )
    op.create_index(op.f('ix_password_reset_codes_email'), 'password_reset_codes', ['email'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_password_reset_codes_email'), table_name='password_reset_codes')
    op.drop_table('password_reset_codes')
