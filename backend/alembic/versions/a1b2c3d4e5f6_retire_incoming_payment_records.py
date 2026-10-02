from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.engine import Connection

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contract (shrink) migration. Run only after the new app version is fully
# deployed and old instances have drained: it drops the structures legacy
# code still writes to. Every preflight runs before any destructive DDL so a
# blocked upgrade leaves the expand-era schema untouched.

ACTIVE_PAYOUT_STATUSES = ("pending_approval", "approved")
_ACTIVE_PAYOUT_STATUS_LIST = ", ".join(
    f"'{status}'" for status in ACTIVE_PAYOUT_STATUSES
)

# Sale events must keep the merchant-provided due date and the external
# payment reference: they are the only correlation left once the
# payment_records table is gone, and ck_events_sale_payment_context relies
# on clean data.
SALE_EVENTS_MISSING_PAYMENT_CONTEXT_SQL = (
    "SELECT 1 FROM events "
    "WHERE type = 'sale' "
    "AND (good_date IS NULL OR payment_record_id IS NULL "
    "OR length(btrim(payment_record_id)) = 0) "
    "LIMIT 1"
)

# An unknown record_type is unmapped data that must be resolved before the
# table can be dropped.
PAYMENT_RECORDS_WITH_UNKNOWN_TYPE_SQL = (
    "SELECT 1 FROM payment_records "
    "WHERE record_type IS NULL "
    "OR record_type NOT IN ('incoming_payment', 'affiliate_payout') "
    "LIMIT 1"
)

# Incoming payments are merchant payment history; dropping them destroys
# data nobody else holds, so any row blocks the retirement until the service
# owner approves a retention path.
INCOMING_PAYMENT_RECORDS_SQL = (
    "SELECT 1 FROM payment_records "
    "WHERE record_type = 'incoming_payment' "
    "LIMIT 1"
)

# A stored PayPal batch id is the only trace of how a legacy batch payout
# was dispatched; dropping the column while values remain loses audit data.
PAYOUTS_WITH_PAYPAL_BATCH_ID_SQL = (
    "SELECT 1 FROM payouts WHERE paypal_batch_id IS NOT NULL LIMIT 1"
)

# Activating every link to an in-flight payout assumes each commission is
# reserved by at most one of them; two would violate the partial unique
# index below when the stale links are flipped on.
COMMISSIONS_WITH_MULTIPLE_INFLIGHT_PAYOUTS_SQL = (
    "SELECT link.commission_id FROM payout_commissions AS link "
    "JOIN payouts AS payout ON payout.id = link.payout_id "
    f"WHERE payout.status IN ({_ACTIVE_PAYOUT_STATUS_LIST}) "
    "GROUP BY link.commission_id "
    "HAVING COUNT(*) > 1 "
    "LIMIT 1"
)

# Stale reservations: a link to an already-closed payout wedges the
# commission (it blocks maturity promotion and re-request) without holding a
# real reservation. Mirror reject_payout/confirm_payout_payment: paid
# payouts settle their commissions, rejected ones release them.
SETTLE_RESERVED_COMMISSIONS_OF_PAID_PAYOUTS_SQL = (
    "UPDATE commissions SET status = 'paid' "
    "WHERE status = 'reserved' AND EXISTS ("
    "SELECT 1 FROM payout_commissions AS link "
    "JOIN payouts AS payout ON payout.id = link.payout_id "
    "WHERE link.commission_id = commissions.id "
    "AND link.is_active IS TRUE "
    "AND payout.status = 'paid'"
    ")"
)

RELEASE_RESERVED_COMMISSIONS_OF_REJECTED_PAYOUTS_SQL = (
    "UPDATE commissions SET status = 'available' "
    "WHERE status = 'reserved' "
    "AND NOT EXISTS ("
    "SELECT 1 FROM payout_commissions AS link "
    "JOIN payouts AS payout ON payout.id = link.payout_id "
    "WHERE link.commission_id = commissions.id "
    "AND link.is_active IS TRUE "
    "AND payout.status = 'paid'"
    ") "
    "AND EXISTS ("
    "SELECT 1 FROM payout_commissions AS link "
    "JOIN payouts AS payout ON payout.id = link.payout_id "
    "WHERE link.commission_id = commissions.id "
    "AND link.is_active IS TRUE "
    "AND payout.status = 'rejected'"
    ")"
)

DEACTIVATE_CLOSED_PAYOUT_LINKS_SQL = (
    "UPDATE payout_commissions SET is_active = FALSE FROM payouts "
    "WHERE payouts.id = payout_commissions.payout_id "
    "AND payouts.status IN ('rejected', 'paid') "
    "AND payout_commissions.is_active IS TRUE"
)

# Links written by old code during the deploy window kept the false default;
# the reservation is real while the parent payout is in-flight.
ACTIVATE_INFLIGHT_PAYOUT_LINKS_SQL = (
    "UPDATE payout_commissions SET is_active = TRUE FROM payouts "
    "WHERE payouts.id = payout_commissions.payout_id "
    f"AND payouts.status IN ({_ACTIVE_PAYOUT_STATUS_LIST}) "
    "AND payout_commissions.is_active IS FALSE"
)

# New code stores linked commissions `reserved`; rows written while old code
# ran may still be `pending` behind a now-active link.
RESERVE_LINKED_PENDING_COMMISSIONS_SQL = (
    "UPDATE commissions SET status = 'reserved' "
    "WHERE status = 'pending' AND EXISTS ("
    "SELECT 1 FROM payout_commissions AS link "
    "JOIN payouts AS payout ON payout.id = link.payout_id "
    "WHERE link.commission_id = commissions.id "
    "AND link.is_active IS TRUE "
    f"AND payout.status IN ({_ACTIVE_PAYOUT_STATUS_LIST})"
    ")"
)

# Mirror mature_due_commissions conservatively: a due pending commission
# with no active reservation becomes available. Rows with NULL available_at
# are left for the runtime job, which derives the due instant from
# events.good_date.
PROMOTE_DUE_UNRESERVED_COMMISSIONS_SQL = (
    "UPDATE commissions SET status = 'available' "
    "WHERE status = 'pending' "
    "AND available_at IS NOT NULL AND available_at <= CURRENT_TIMESTAMP "
    "AND NOT EXISTS ("
    "SELECT 1 FROM payout_commissions AS link "
    "WHERE link.commission_id = commissions.id AND link.is_active IS TRUE"
    ")"
)

# Catch affiliate_payout rows written by old code after f9a0b1c2d3e4 already
# ran; ids and payout links are preserved one-for-one.
COPY_AFFILIATE_PAYOUT_RECORDS_SQL = (
    "INSERT INTO payout_payments "
    "(id, payout_id, amount, currency, payment_method, transfer_reference, "
    "paid_at, recorded_by_tenant_user_id, created_at) "
    "SELECT id, payout_id, amount, currency, payment_method, "
    "transfer_reference, paid_at, recorded_by_tenant_user_id, "
    "COALESCE(created_at, CURRENT_TIMESTAMP) "
    "FROM payment_records "
    "WHERE record_type = 'affiliate_payout' "
    "ON CONFLICT (payout_id) DO NOTHING"
)

# Every affiliate_payout source row must have an identical
# payout_payments counterpart — including rows the ON CONFLICT clause
# skipped because new code already recorded the payment differently.
AFFILIATE_PAYOUT_RECORD_MISMATCH_SQL = (
    "SELECT 1 FROM payment_records AS record "
    "LEFT JOIN payout_payments AS payment "
    "ON payment.payout_id = record.payout_id "
    "WHERE record.record_type = 'affiliate_payout' "
    "AND (payment.id IS NULL "
    "OR payment.amount IS DISTINCT FROM record.amount "
    "OR payment.currency IS DISTINCT FROM record.currency "
    "OR payment.payment_method IS DISTINCT FROM record.payment_method "
    "OR payment.transfer_reference IS DISTINCT FROM record.transfer_reference "
    "OR payment.paid_at IS DISTINCT FROM record.paid_at "
    "OR payment.recorded_by_tenant_user_id "
    "IS DISTINCT FROM record.recorded_by_tenant_user_id) "
    "LIMIT 1"
)


def _assert_no_rows(connection: Connection, query: str, message: str) -> None:
    if connection.execute(sa.text(query)).first():
        raise RuntimeError(message)


def run_preflight(connection: Connection) -> None:
    """Fail closed before any DDL when existing data cannot be retired."""
    _assert_no_rows(
        connection,
        SALE_EVENTS_MISSING_PAYMENT_CONTEXT_SQL,
        "Cannot retire payment records while sale events lack a good_date "
        "or external payment_record_id",
    )
    _assert_no_rows(
        connection,
        PAYMENT_RECORDS_WITH_UNKNOWN_TYPE_SQL,
        "Cannot retire payment_records while a record_type outside "
        "incoming_payment or affiliate_payout exists",
    )
    _assert_no_rows(
        connection,
        INCOMING_PAYMENT_RECORDS_SQL,
        "Cannot retire payment_records while incoming_payment rows exist; "
        "stop before dropping the table — retention must be resolved by "
        "the service owner",
    )
    _assert_no_rows(
        connection,
        PAYOUTS_WITH_PAYPAL_BATCH_ID_SQL,
        "Cannot retire payment records while payouts.paypal_batch_id "
        "values remain",
    )
    _assert_no_rows(
        connection,
        COMMISSIONS_WITH_MULTIPLE_INFLIGHT_PAYOUTS_SQL,
        "Cannot retire payment records while a commission is linked to "
        "more than one pending_approval or approved payout",
    )


def _assert_prerequisite_structures(connection: Connection) -> None:
    """The reconciliation below relies on expand-revision structures."""
    for name in ("ck_commissions_status", "ck_payouts_status"):
        exists = connection.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint "
                "WHERE conname = :name AND contype = 'c'"
            ),
            {"name": name},
        ).first()
        if not exists:
            raise RuntimeError(
                f"Cannot retire payment records without the {name} "
                "check constraint created by earlier revisions"
            )
    indexdef = connection.execute(
        sa.text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' "
            "AND indexname = 'uq_payout_commissions_active_commission'"
        )
    ).scalar()
    if (
        indexdef is None
        or "UNIQUE" not in indexdef.upper()
        or "is_active" not in indexdef
    ):
        raise RuntimeError(
            "Cannot retire payment records without the partial unique "
            "uq_payout_commissions_active_commission index created by "
            "earlier revisions"
        )


def upgrade() -> None:
    connection = op.get_bind()
    run_preflight(connection)
    _assert_prerequisite_structures(connection)

    # Reconcile reservation state left behind by old app versions before the
    # structures it depends on are dropped.
    op.execute(sa.text(SETTLE_RESERVED_COMMISSIONS_OF_PAID_PAYOUTS_SQL))
    op.execute(sa.text(RELEASE_RESERVED_COMMISSIONS_OF_REJECTED_PAYOUTS_SQL))
    op.execute(sa.text(DEACTIVATE_CLOSED_PAYOUT_LINKS_SQL))
    op.execute(sa.text(ACTIVATE_INFLIGHT_PAYOUT_LINKS_SQL))
    op.execute(sa.text(RESERVE_LINKED_PENDING_COMMISSIONS_SQL))
    op.execute(sa.text(PROMOTE_DUE_UNRESERVED_COMMISSIONS_SQL))

    op.execute(sa.text(COPY_AFFILIATE_PAYOUT_RECORDS_SQL))
    _assert_no_rows(
        connection,
        AFFILIATE_PAYOUT_RECORD_MISMATCH_SQL,
        "Cannot retire payment_records while an affiliate_payout row lacks "
        "a matching payout_payments counterpart",
    )

    op.create_check_constraint(
        "ck_events_sale_payment_context",
        "events",
        "type <> 'sale' OR (good_date IS NOT NULL "
        "AND payment_record_id IS NOT NULL "
        "AND length(btrim(payment_record_id)) > 0)",
    )

    op.drop_column("commissions", "available_on")
    op.drop_table("payment_records")
    op.drop_column("payouts", "paypal_batch_id")

    op.create_index(
        "ix_payouts_affiliate_requested_at",
        "payouts",
        ["affiliate_id", "requested_at"],
    )


def downgrade() -> None:
    # Copied payment rows, notification state, and commission history cannot
    # be merged back into the legacy structures without fabricating or
    # losing audit data, so refuse to downgrade once they exist.
    connection = op.get_bind()
    _assert_no_rows(
        connection,
        "SELECT 1 FROM payout_payments LIMIT 1",
        "Cannot downgrade payment-record retirement while payout_payments rows exist",
    )
    _assert_no_rows(
        connection,
        "SELECT 1 FROM payout_notifications LIMIT 1",
        "Cannot downgrade payment-record retirement while payout_notifications rows exist",
    )
    _assert_no_rows(
        connection,
        "SELECT 1 FROM commissions LIMIT 1",
        "Cannot downgrade payment-record retirement while commissions exist",
    )
    _assert_no_rows(
        connection,
        "SELECT 1 FROM payout_commissions LIMIT 1",
        "Cannot downgrade payment-record retirement while payout commission links exist",
    )

    op.drop_index("ix_payouts_affiliate_requested_at", table_name="payouts")
    op.add_column(
        "payouts", sa.Column("paypal_batch_id", sa.String(), nullable=True)
    )
    op.add_column(
        "commissions", sa.Column("available_on", sa.Date(), nullable=True)
    )
    op.drop_constraint(
        "ck_events_sale_payment_context", "events", type_="check"
    )
    # Restore only the empty legacy table exactly as f9a0b1c2d3e4 left it;
    # historical rows are never fabricated.
    op.create_table(
        "payment_records",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_payment_id", sa.String(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.String(), nullable=True),
        sa.Column("amount", sa.Numeric(20, 2), nullable=False),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sequence_number", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column(
            "record_type",
            sa.String(),
            nullable=False,
            server_default="incoming_payment",
        ),
        sa.Column("payout_id", sa.UUID(), nullable=True),
        sa.Column("payment_method", sa.String(), nullable=True),
        sa.Column("transfer_reference", sa.String(), nullable=True),
        sa.Column("recorded_by_tenant_user_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["payout_id"],
            ["payouts.id"],
            name="fk_payment_records_payout_id_payouts",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_tenant_user_id"],
            ["tenant_users.id"],
            name="fk_payment_records_recorded_by_tenant_user_id_tenant_users",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payout_id", name="uq_payment_records_payout_id"),
    )
    op.create_index(
        "ix_payment_records_tenant_payment_id",
        "payment_records",
        ["tenant_payment_id"],
    )
