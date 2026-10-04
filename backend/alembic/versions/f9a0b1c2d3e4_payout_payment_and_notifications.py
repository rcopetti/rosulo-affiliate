from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "f9a0b1c2d3e4"
down_revision: str | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAYOUT_STATUSES = ("pending_approval", "approved", "rejected", "paid")
_PAYOUT_STATUS_LIST = ", ".join(f"'{status}'" for status in PAYOUT_STATUSES)

NOTIFICATION_STATUSES = ("pending", "sending", "sent", "failed")
_NOTIFICATION_STATUS_LIST = ", ".join(
    f"'{status}'" for status in NOTIFICATION_STATUSES
)

# Every payout settlement record must carry the full audit fields before it
# can be re-homed in payout_payments; anything missing is unrecoverable
# legacy data and must be reconciled by hand first.
AFFILIATE_PAYOUT_RECORDS_MISSING_FIELDS_SQL = (
    "SELECT 1 FROM payment_records "
    "WHERE record_type = 'affiliate_payout' "
    "AND (payout_id IS NULL "
    "OR transfer_reference IS NULL OR length(btrim(transfer_reference)) = 0 "
    "OR payment_method IS NULL OR length(btrim(payment_method)) = 0 "
    "OR amount IS NULL "
    "OR currency IS NULL OR length(btrim(currency)) = 0 "
    "OR paid_at IS NULL "
    "OR recorded_by_tenant_user_id IS NULL) "
    "LIMIT 1"
)

# Only incoming payments and affiliate payouts are known record types; an
# unexpected value means unmapped data that must be resolved first.
PAYMENT_RECORDS_WITH_UNKNOWN_TYPE_SQL = (
    "SELECT 1 FROM payment_records "
    "WHERE record_type IS NULL "
    "OR record_type NOT IN ('incoming_payment', 'affiliate_payout') "
    "LIMIT 1"
)

# The payout status check constraint cannot be added while a stored status
# falls outside the manual settlement states.
PAYOUTS_WITH_UNKNOWN_STATUS_SQL = (
    "SELECT 1 FROM payouts "
    "WHERE status IS NULL "
    f"OR status NOT IN ({_PAYOUT_STATUS_LIST}) "
    "LIMIT 1"
)

# Rows move one-for-one; ids are preserved so audit references stay stable.
# payment_records itself is left intact for the separate retirement gate.
COPY_AFFILIATE_PAYOUT_RECORDS_SQL = (
    "INSERT INTO payout_payments "
    "(id, payout_id, amount, currency, payment_method, transfer_reference, "
    "paid_at, recorded_by_tenant_user_id, created_at) "
    "SELECT id, payout_id, amount, currency, payment_method, "
    "transfer_reference, paid_at, recorded_by_tenant_user_id, "
    "COALESCE(created_at, CURRENT_TIMESTAMP) "
    "FROM payment_records "
    "WHERE record_type = 'affiliate_payout'"
)


def _assert_no_rows(connection: Connection, query: str, message: str) -> None:
    if connection.execute(sa.text(query)).first():
        raise RuntimeError(message)


def run_preflight(connection: Connection) -> None:
    """Fail closed before any DDL when existing data cannot be migrated."""
    _assert_no_rows(
        connection,
        AFFILIATE_PAYOUT_RECORDS_MISSING_FIELDS_SQL,
        "Cannot migrate affiliate_payout payment records while rows lack "
        "a payout_id, transfer_reference, payment_method, amount, currency, "
        "paid_at, or recorded_by_tenant_user_id",
    )
    _assert_no_rows(
        connection,
        PAYMENT_RECORDS_WITH_UNKNOWN_TYPE_SQL,
        "Cannot migrate payment records while a record_type outside "
        "incoming_payment or affiliate_payout exists",
    )
    _assert_no_rows(
        connection,
        PAYOUTS_WITH_UNKNOWN_STATUS_SQL,
        "Cannot constrain payout statuses while payouts have a status "
        "outside pending_approval, approved, rejected, or paid",
    )


def upgrade() -> None:
    connection = op.get_bind()
    run_preflight(connection)

    op.create_table(
        "payout_payments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("payout_id", sa.UUID(), nullable=False),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("payment_method", sa.String(), nullable=False),
        sa.Column("transfer_reference", sa.String(), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_tenant_user_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["payout_id"], ["payouts.id"]),
        sa.ForeignKeyConstraint(["recorded_by_tenant_user_id"], ["tenant_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payout_id", name="uq_payout_payments_payout_id"),
    )

    op.execute(sa.text(COPY_AFFILIATE_PAYOUT_RECORDS_SQL))
    source_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM payment_records "
            "WHERE record_type = 'affiliate_payout'"
        )
    ).scalar_one()
    copied_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM payout_payments")
    ).scalar_one()
    if copied_count != source_count:
        raise RuntimeError(
            "Copied payout payment count does not match affiliate_payout "
            "payment_records count"
        )

    op.create_table(
        "payout_notifications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("payout_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["payout_id"], ["payouts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payout_id", name="uq_payout_notifications_payout_id"),
        sa.CheckConstraint(
            f"status IN ({_NOTIFICATION_STATUS_LIST})",
            name="ck_payout_notifications_status",
        ),
    )

    op.create_check_constraint(
        "ck_payouts_status",
        "payouts",
        f"status IN ({_PAYOUT_STATUS_LIST})",
    )
    op.alter_column(
        "payouts",
        "status",
        existing_type=sa.String(),
        nullable=False,
        server_default="pending_approval",
    )


def downgrade() -> None:
    # Copied payment rows and notification delivery state cannot be merged
    # back into the overloaded payment_records table without losing audit
    # history, so refuse to downgrade once they exist.
    connection = op.get_bind()
    _assert_no_rows(
        connection,
        "SELECT 1 FROM payout_payments LIMIT 1",
        "Cannot downgrade payout payments while payout_payments rows exist",
    )
    _assert_no_rows(
        connection,
        "SELECT 1 FROM payout_notifications LIMIT 1",
        "Cannot downgrade payout payment notifications while payout_notifications rows exist",
    )

    op.alter_column(
        "payouts",
        "status",
        existing_type=sa.String(),
        nullable=True,
        server_default=None,
    )
    op.drop_constraint("ck_payouts_status", "payouts", type_="check")
    op.drop_table("payout_notifications")
    op.drop_table("payout_payments")
