from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY_COLUMNS = (
    ("events", "amount"),
    ("payment_records", "amount"),
    ("commissions", "gross_amount"),
    ("commissions", "withholding_amount"),
    ("commissions", "net_amount"),
    ("payouts", "requested_amount"),
    ("payouts", "approved_amount"),
    ("payouts", "withholding_total"),
    ("payouts", "paypal_fees"),
    ("payouts", "net_paid"),
    ("payout_commissions", "amount"),
)


def _assert_no_rows(query: str, message: str) -> None:
    if op.get_bind().execute(sa.text(query)).first():
        raise RuntimeError(message)


def _preflight() -> None:
    for table, column in MONEY_COLUMNS:
        _assert_no_rows(
            f"SELECT 1 FROM {table} WHERE {column} IS NULL LIMIT 1",
            f"Cannot migrate {table}.{column}: NULL monetary values require review",
        )
    for table in ("events", "payment_records", "commissions", "payouts"):
        _assert_no_rows(
            f"SELECT 1 FROM {table} WHERE currency IS NULL LIMIT 1",
            f"Cannot migrate {table}: NULL currency values require review",
        )

    _assert_no_rows(
        "SELECT 1 FROM commissions WHERE currency NOT IN ('USD', 'EUR', 'BRL') LIMIT 1",
        "Cannot migrate commissions with currencies outside USD/EUR/BRL",
    )
    _assert_no_rows(
        "SELECT 1 FROM payouts WHERE currency NOT IN ('USD', 'EUR', 'BRL') LIMIT 1",
        "Cannot migrate payouts with currencies outside USD/EUR/BRL",
    )
    _assert_no_rows(
        "SELECT 1 FROM commissions c JOIN events e ON e.id = c.event_id "
        "WHERE c.currency IS DISTINCT FROM e.currency LIMIT 1",
        "Cannot migrate commissions whose currency differs from their source event",
    )
    _assert_no_rows(
        "SELECT 1 FROM payout_commissions pc "
        "JOIN commissions c ON c.id = pc.commission_id "
        "JOIN payouts p ON p.id = pc.payout_id "
        "WHERE p.currency IS DISTINCT FROM c.currency LIMIT 1",
        "Cannot migrate payouts whose currency differs from a linked commission",
    )
    _assert_no_rows(
        "SELECT 1 FROM payout_commissions pc "
        "JOIN commissions c ON c.id = pc.commission_id "
        "GROUP BY pc.payout_id HAVING count(DISTINCT c.currency) > 1 LIMIT 1",
        "Cannot migrate a payout linked to commissions in multiple currencies",
    )


def upgrade() -> None:
    _preflight()
    for table, column in MONEY_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.Float(),
            type_=sa.Numeric(20, 2),
            postgresql_using=f"round({column}::numeric, 2)",
        )
    op.alter_column(
        "terms",
        "minimum_threshold",
        existing_type=sa.Float(),
        type_=sa.Numeric(20, 2),
        postgresql_using="round(minimum_threshold::numeric, 2)",
    )
    op.alter_column(
        "terms",
        "commission_percent",
        existing_type=sa.Float(),
        type_=sa.Numeric(9, 6),
        postgresql_using="round(commission_percent::numeric, 6)",
    )
    op.add_column("events", sa.Column("commission_status", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "commission_status")
    op.alter_column(
        "terms",
        "commission_percent",
        existing_type=sa.Numeric(9, 6),
        type_=sa.Float(),
        postgresql_using="commission_percent::double precision",
    )
    op.alter_column(
        "terms",
        "minimum_threshold",
        existing_type=sa.Numeric(20, 2),
        type_=sa.Float(),
        postgresql_using="minimum_threshold::double precision",
    )
    for table, column in reversed(MONEY_COLUMNS):
        op.alter_column(
            table,
            column,
            existing_type=sa.Numeric(20, 2),
            type_=sa.Float(),
            postgresql_using=f"{column}::double precision",
        )
