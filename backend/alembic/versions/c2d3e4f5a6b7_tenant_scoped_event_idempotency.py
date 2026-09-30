"""scope event idempotency to tenant

Revision ID: c2d3e4f5a6b7
Revises: f7a8b9c0d123
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | None = "f7a8b9c0d123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_events_event_id", table_name="events")
    op.create_unique_constraint(
        "uq_events_tenant_id_event_id",
        "events",
        ["tenant_id", "event_id"],
    )


def downgrade() -> None:
    duplicate = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM events "
            "GROUP BY event_id HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate:
        raise RuntimeError(
            "Cannot restore global event_id uniqueness while cross-tenant duplicates exist"
        )

    op.drop_constraint(
        "uq_events_tenant_id_event_id",
        "events",
        type_="unique",
    )
    op.create_index("ix_events_event_id", "events", ["event_id"], unique=True)
