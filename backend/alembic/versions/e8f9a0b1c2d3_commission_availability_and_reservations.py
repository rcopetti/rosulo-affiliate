from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_PAYOUT_STATUSES = ("pending_approval", "approved")
_ACTIVE_PAYOUT_STATUS_LIST = ", ".join(
    f"'{status}'" for status in ACTIVE_PAYOUT_STATUSES
)

# Sale events must carry the merchant-provided due date and the external
# payment reference before commissions can derive `available_at` from them.
# `occurred_at` is never a substitute and no external payment ID is invented.
SALE_EVENTS_MISSING_DUE_DATE_SQL = (
    "SELECT 1 FROM events "
    "WHERE type = 'sale' "
    "AND (good_date IS NULL OR payment_record_id IS NULL "
    "OR length(btrim(payment_record_id)) = 0) "
    "LIMIT 1"
)

# Legacy `requested`, `processing`, or `failed` payouts must be reconciled
# before active reservations can be derived from payout status.
PAYOUTS_WITH_UNKNOWN_STATUS_SQL = (
    "SELECT 1 FROM payouts "
    "WHERE status IS NULL "
    f"OR status NOT IN ({_ACTIVE_PAYOUT_STATUS_LIST}, 'rejected', 'paid') "
    "LIMIT 1"
)

# `reserved` is introduced by this revision; pre-migration rows must only use
# the legacy states so no stored status has to be rewritten while old app
# versions still run.
COMMISSIONS_WITH_UNKNOWN_STATUS_SQL = (
    "SELECT 1 FROM commissions "
    "WHERE status IS NULL "
    "OR status NOT IN ('pending', 'available', 'paid', 'reversed') "
    "LIMIT 1"
)

# A commission linked to more than one pending_approval/approved payout cannot
# satisfy the single-active-reservation invariant.
COMMISSIONS_WITH_MULTIPLE_ACTIVE_PAYOUTS_SQL = (
    "SELECT link.commission_id FROM payout_commissions AS link "
    "JOIN payouts AS payout ON payout.id = link.payout_id "
    f"WHERE payout.status IN ({_ACTIVE_PAYOUT_STATUS_LIST}) "
    "GROUP BY link.commission_id "
    "HAVING COUNT(*) > 1 "
    "LIMIT 1"
)

# `available_at` is the merchant due date interpreted as 00:00 UTC. It is never
# derived from the legacy `available_on` hold date.
BACKFILL_COMMISSION_AVAILABLE_AT_SQL = (
    "UPDATE commissions "
    "SET available_at = (events.good_date::timestamp AT TIME ZONE 'UTC') "
    "FROM events "
    "WHERE events.id = commissions.event_id AND events.good_date IS NOT NULL"
)

# Existing links to in-flight payouts become active reservations. Old app
# versions insert links without this column, so they land with the false
# default and runtime checks must keep consulting the parent payout status.
BACKFILL_PAYOUT_COMMISSION_IS_ACTIVE_SQL = (
    "UPDATE payout_commissions SET is_active = TRUE FROM payouts "
    "WHERE payouts.id = payout_commissions.payout_id "
    f"AND payouts.status IN ({_ACTIVE_PAYOUT_STATUS_LIST})"
)


def _assert_no_rows(connection: Connection, query: str, message: str) -> None:
    if connection.execute(sa.text(query)).first():
        raise RuntimeError(message)


def run_preflight(connection: Connection) -> None:
    """Fail closed before any DDL when existing data cannot be migrated."""
    _assert_no_rows(
        connection,
        SALE_EVENTS_MISSING_DUE_DATE_SQL,
        "Cannot migrate commission availability while sale events lack "
        "a good_date or external payment_record_id",
    )
    _assert_no_rows(
        connection,
        PAYOUTS_WITH_UNKNOWN_STATUS_SQL,
        "Cannot migrate payout reservations while payouts have a status "
        "outside pending_approval, approved, rejected, or paid",
    )
    _assert_no_rows(
        connection,
        COMMISSIONS_WITH_UNKNOWN_STATUS_SQL,
        "Cannot migrate commission availability while commissions have a "
        "status outside pending, available, paid, or reversed",
    )
    _assert_no_rows(
        connection,
        COMMISSIONS_WITH_MULTIPLE_ACTIVE_PAYOUTS_SQL,
        "Cannot migrate payout reservations while a commission is linked to "
        "more than one pending_approval or approved payout",
    )


def upgrade() -> None:
    run_preflight(op.get_bind())

    op.add_column(
        "commissions",
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text(BACKFILL_COMMISSION_AVAILABLE_AT_SQL))

    op.add_column(
        "payout_commissions",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.execute(sa.text(BACKFILL_PAYOUT_COMMISSION_IS_ACTIVE_SQL))

    op.create_check_constraint(
        "ck_commissions_status",
        "commissions",
        "status IN ('pending', 'available', 'reserved', 'paid', 'reversed')",
    )
    op.create_index(
        "uq_payout_commissions_active_commission",
        "payout_commissions",
        ["commission_id"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
    )


def downgrade() -> None:
    # Merchant due dates cannot be translated back into the old 14-day hold
    # policy, and historical reservation flags cannot be reconstructed.
    connection = op.get_bind()
    _assert_no_rows(
        connection,
        "SELECT 1 FROM commissions LIMIT 1",
        "Cannot downgrade commission availability while commissions exist",
    )
    _assert_no_rows(
        connection,
        "SELECT 1 FROM payout_commissions LIMIT 1",
        "Cannot downgrade commission availability while payout commission links exist",
    )

    op.drop_index(
        "uq_payout_commissions_active_commission",
        table_name="payout_commissions",
    )
    op.drop_constraint("ck_commissions_status", "commissions", type_="check")
    op.drop_column("payout_commissions", "is_active")
    op.drop_column("commissions", "available_at")
