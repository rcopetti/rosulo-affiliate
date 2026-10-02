import uuid
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "a9b0c1d2e3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _assert_no_rows(query: str, message: str) -> None:
    if op.get_bind().execute(sa.text(query)).first():
        raise RuntimeError(message)


def upgrade() -> None:
    _assert_no_rows(
        "SELECT 1 FROM payouts WHERE status IS NULL LIMIT 1",
        "Cannot create payout history for payouts with NULL status",
    )
    _assert_no_rows(
        "SELECT 1 FROM commissions AS commission "
        "JOIN events AS event ON event.id = commission.event_id "
        "WHERE commission.status IN ('pending', 'available') "
        "AND event.good_date IS NULL AND event.occurred_at IS NULL LIMIT 1",
        "Cannot apply payout holds to commissions without a sale date",
    )

    op.alter_column(
        "payment_records",
        "tenant_payment_id",
        existing_type=sa.String(),
        nullable=True,
    )
    op.add_column(
        "payment_records",
        sa.Column(
            "record_type",
            sa.String(),
            nullable=False,
            server_default="incoming_payment",
        ),
    )
    op.add_column("payment_records", sa.Column("payout_id", sa.UUID(), nullable=True))
    op.add_column("payment_records", sa.Column("payment_method", sa.String(), nullable=True))
    op.add_column("payment_records", sa.Column("transfer_reference", sa.String(), nullable=True))
    op.add_column(
        "payment_records",
        sa.Column("recorded_by_tenant_user_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_payment_records_payout_id_payouts",
        "payment_records",
        "payouts",
        ["payout_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_payment_records_recorded_by_tenant_user_id_tenant_users",
        "payment_records",
        "tenant_users",
        ["recorded_by_tenant_user_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_payment_records_payout_id", "payment_records", ["payout_id"]
    )

    op.create_table(
        "payout_transitions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("payout_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(), nullable=True),
        sa.Column("to_status", sa.String(), nullable=False),
        sa.Column("actor_tenant_user_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["payout_id"], ["payouts.id"]),
        sa.ForeignKeyConstraint(["actor_tenant_user_id"], ["tenant_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payout_id", "sequence"),
    )
    op.create_index(
        "ix_payout_transitions_payout_id",
        "payout_transitions",
        ["payout_id"],
    )

    op.execute(
        sa.text(
            "UPDATE commissions AS commission "
            "SET available_on = COALESCE(event.good_date, event.occurred_at::date) + 14, "
            "status = CASE "
            "WHEN commission.status = 'available' "
            "AND COALESCE(event.good_date, event.occurred_at::date) + 14 > CURRENT_DATE "
            "THEN 'pending' ELSE commission.status END "
            "FROM events AS event "
            "WHERE commission.event_id = event.id "
            "AND commission.status IN ('pending', 'available')"
        )
    )

    transition_table = sa.table(
        "payout_transitions",
        sa.column("id", sa.UUID()),
        sa.column("payout_id", sa.UUID()),
        sa.column("sequence", sa.Integer()),
        sa.column("from_status", sa.String()),
        sa.column("to_status", sa.String()),
        sa.column("actor_tenant_user_id", sa.UUID()),
        sa.column("reason", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    legacy_payouts = op.get_bind().execute(
        sa.text(
            "SELECT id, status, "
            "COALESCE(updated_at, requested_at, created_at, CURRENT_TIMESTAMP) AS created_at "
            "FROM payouts"
        )
    )
    op.bulk_insert(
        transition_table,
        [
            {
                "id": uuid.uuid4(),
                "payout_id": row.id,
                "sequence": 1,
                "from_status": None,
                "to_status": row.status,
                "actor_tenant_user_id": None,
                "reason": "Legacy payout state at manual settlement migration",
                "created_at": row.created_at,
            }
            for row in legacy_payouts
        ],
    )


def downgrade() -> None:
    _assert_no_rows(
        "SELECT 1 FROM payout_transitions LIMIT 1",
        "Cannot downgrade manual payout settlement while payout transition history exists",
    )
    _assert_no_rows(
        "SELECT 1 FROM payment_records WHERE payout_id IS NOT NULL LIMIT 1",
        "Cannot downgrade manual payout settlement while payout payment records exist",
    )
    _assert_no_rows(
        "SELECT 1 FROM commissions WHERE status IN ('pending', 'available') LIMIT 1",
        "Cannot downgrade manual payout settlement while commission hold dates need review",
    )
    _assert_no_rows(
        "SELECT 1 FROM payment_records WHERE tenant_payment_id IS NULL LIMIT 1",
        "Cannot downgrade manual payout settlement while payment records have no tenant payment ID",
    )

    op.drop_index("ix_payout_transitions_payout_id", table_name="payout_transitions")
    op.drop_table("payout_transitions")
    op.drop_constraint("uq_payment_records_payout_id", "payment_records", type_="unique")
    op.drop_constraint(
        "fk_payment_records_recorded_by_tenant_user_id_tenant_users",
        "payment_records",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_payment_records_payout_id_payouts",
        "payment_records",
        type_="foreignkey",
    )
    op.drop_column("payment_records", "recorded_by_tenant_user_id")
    op.drop_column("payment_records", "transfer_reference")
    op.drop_column("payment_records", "payment_method")
    op.drop_column("payment_records", "payout_id")
    op.drop_column("payment_records", "record_type")
    op.alter_column(
        "payment_records",
        "tenant_payment_id",
        existing_type=sa.String(),
        nullable=False,
    )
