import contextlib
import importlib.util
import os
import subprocess
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

import asyncpg
import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine.url import make_url

from app.core.config import settings
from app.db.models import (
    Affiliate,
    AffiliateAccount,
    Payout,
    PayoutNotification,
    PayoutPayment,
    Tenant,
    TenantUser,
)
from app.db.session import async_session, engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    BACKEND_DIR
    / "alembic"
    / "versions"
    / "f9a0b1c2d3e4_payout_payment_and_notifications.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "f9a0b1c2d3e4_payout_payment_and_notifications", MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MIGRATION = _load_migration_module()

# The ORM no longer maps payment_records; recreate the shape f9a0b1c2d3e4
# operated on so its preflight can still be exercised against the test DB.
LEGACY_PAYMENT_RECORDS_DDL = """
CREATE TABLE payment_records (
    id UUID PRIMARY KEY,
    tenant_payment_id VARCHAR,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    customer_id VARCHAR,
    amount NUMERIC(20,2) NOT NULL,
    currency VARCHAR,
    paid_at TIMESTAMPTZ,
    sequence_number INTEGER,
    status VARCHAR,
    record_type VARCHAR NOT NULL,
    payout_id UUID REFERENCES payouts(id),
    payment_method VARCHAR,
    transfer_reference VARCHAR,
    recorded_by_tenant_user_id UUID REFERENCES tenant_users(id),
    created_at TIMESTAMPTZ
)
"""


@contextlib.asynccontextmanager
async def _legacy_payment_records_table():
    async with engine.begin() as conn:
        await conn.execute(sa.text("DROP TABLE IF EXISTS payment_records"))
        await conn.execute(sa.text(LEGACY_PAYMENT_RECORDS_DDL))
    try:
        yield
    finally:
        async with engine.begin() as conn:
            await conn.execute(sa.text("DROP TABLE IF EXISTS payment_records"))


def _disposable_dsn(database: str) -> str:
    url = make_url(settings.database_url).set(database=database)
    password = f":{url.password}" if url.password else ""
    port = f":{url.port}" if url.port else ""
    return f"postgresql://{url.username}{password}@{url.host}{port}/{url.database}"


def _alembic_url(database: str) -> str:
    return make_url(settings.database_url).set(database=database).render_as_string(
        hide_password=False
    )


def _run_alembic(database: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": _alembic_url(database)}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


async def _create_disposable_database() -> str:
    database = f"payout_migration_{uuid.uuid4().hex[:12]}"
    conn = await asyncpg.connect(_disposable_dsn("postgres"))
    try:
        await conn.execute(f'CREATE DATABASE "{database}"')
    finally:
        await conn.close()
    return database


async def _drop_disposable_database(database: str) -> None:
    conn = await asyncpg.connect(_disposable_dsn("postgres"))
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{database}" WITH (FORCE)')
    finally:
        await conn.close()


async def _insert_org(conn) -> dict:
    """Tenant + admin user + affiliate account + affiliate; returns their ids."""
    ids = {key: uuid.uuid4() for key in ("tenant", "user", "account", "affiliate")}
    await conn.execute(
        "INSERT INTO tenants (id, name, api_key_hash) VALUES ($1, 'acme', 'hash')",
        ids["tenant"],
    )
    await conn.execute(
        "INSERT INTO tenant_users (id, tenant_id, email, password_hash, role) "
        "VALUES ($1, $2, $3, 'hash', 'admin')",
        ids["user"],
        ids["tenant"],
        f"admin-{uuid.uuid4()}@example.com",
    )
    await conn.execute(
        "INSERT INTO affiliate_accounts "
        "(id, email, password_hash, name, country, tax_status) "
        "VALUES ($1, $2, 'hash', 'Affiliate', 'US', 'us_person')",
        ids["account"],
        f"affiliate-{uuid.uuid4()}@example.com",
    )
    await conn.execute(
        "INSERT INTO affiliates (id, affiliate_account_id, tenant_id) "
        "VALUES ($1, $2, $3)",
        ids["affiliate"],
        ids["account"],
        ids["tenant"],
    )
    return ids


async def _insert_payout(conn, ids, status: str, **overrides) -> uuid.UUID:
    payout_id = overrides.pop("id", uuid.uuid4())
    columns = ["id", "affiliate_id", "tenant_id", "status", "currency"]
    values = [payout_id, ids["affiliate"], ids["tenant"], status, "USD"]
    for column, value in overrides.items():
        columns.append(column)
        values.append(value)
    placeholders = ", ".join(f"${index}" for index in range(1, len(values) + 1))
    await conn.execute(
        f"INSERT INTO payouts ({', '.join(columns)}) VALUES ({placeholders})",
        *values,
    )
    return payout_id


async def _insert_sale_event(conn, ids, suffix: str, **overrides) -> uuid.UUID:
    event_id = overrides.pop("id", uuid.uuid4())
    values = {
        "id": event_id,
        "event_id": f"sale-{suffix}-{uuid.uuid4()}",
        "type": "sale",
        "tenant_id": ids["tenant"],
        "affiliate_id": ids["affiliate"],
        "good_date": date(2026, 1, 15),
        "payment_record_id": f"external-{suffix}",
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f"${index}" for index in range(1, len(values) + 1))
    await conn.execute(
        f"INSERT INTO events ({columns}) VALUES ({placeholders})",
        *values.values(),
    )
    return event_id


async def _insert_commission(
    conn, ids, event_id, status: str, *, available_at=None
) -> uuid.UUID:
    commission_id = uuid.uuid4()
    await conn.execute(
        "INSERT INTO commissions "
        "(id, event_id, affiliate_id, gross_amount, withholding_amount, "
        "net_amount, currency, status, available_at, created_at, updated_at) "
        "VALUES ($1, $2, $3, 10.00, 0.00, 10.00, 'USD', $4, $5, now(), now())",
        commission_id,
        event_id,
        ids["affiliate"],
        status,
        available_at,
    )
    return commission_id


async def _insert_payout_commission(
    conn, payout_id, commission_id, is_active: bool
) -> uuid.UUID:
    link_id = uuid.uuid4()
    await conn.execute(
        "INSERT INTO payout_commissions "
        "(id, payout_id, commission_id, amount, is_active) "
        "VALUES ($1, $2, $3, 10.00, $4)",
        link_id,
        payout_id,
        commission_id,
        is_active,
    )
    return link_id


async def _insert_payment_record(conn, ids, record_type: str, **overrides):
    record_id = overrides.pop("id", uuid.uuid4())
    values = {
        "id": record_id,
        "tenant_id": ids["tenant"],
        "amount": Decimal("12.34"),
        "currency": "USD",
        "paid_at": datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc),
        "status": "paid",
        "record_type": record_type,
        "created_at": datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc),
    }
    values.update(overrides)
    columns = ", ".join(values)
    placeholders = ", ".join(f"${index}" for index in range(1, len(values) + 1))
    await conn.execute(
        f"INSERT INTO payment_records ({columns}) VALUES ({placeholders})",
        *values.values(),
    )
    return record_id


async def _alembic_version(database: str) -> str:
    conn = await asyncpg.connect(_disposable_dsn(database))
    try:
        return await conn.fetchval("SELECT version_num FROM alembic_version")
    finally:
        await conn.close()


async def _create_affiliate_payout_record(session, **overrides):
    tenant = Tenant(name="acme", api_key_hash=f"hash-{uuid.uuid4()}")
    account = AffiliateAccount(
        email=f"affiliate-{uuid.uuid4()}@example.com",
        password_hash="hash",
        name="Affiliate",
        country="US",
    )
    session.add_all([tenant, account])
    await session.flush()
    user = TenantUser(
        tenant_id=tenant.id,
        email=f"admin-{uuid.uuid4()}@example.com",
        password_hash="hash",
        role="admin",
    )
    affiliate = Affiliate(affiliate_account_id=account.id, tenant_id=tenant.id)
    session.add_all([user, affiliate])
    await session.flush()
    payout = Payout(affiliate_id=affiliate.id, tenant_id=tenant.id, status="paid")
    session.add(payout)
    await session.flush()
    values = {
        "id": uuid.uuid4(),
        "tenant_id": tenant.id,
        "amount": Decimal("12.34"),
        "currency": "USD",
        "paid_at": datetime.now(timezone.utc),
        "status": "paid",
        "record_type": "affiliate_payout",
        "payout_id": payout.id,
        "payment_method": "paypal",
        "transfer_reference": f"ref-{uuid.uuid4()}",
        "recorded_by_tenant_user_id": user.id,
        "created_at": datetime.now(timezone.utc),
    }
    values.update(overrides)
    await session.execute(
        sa.text(
            "INSERT INTO payment_records "
            "(id, tenant_id, amount, currency, paid_at, status, record_type, "
            "payout_id, payment_method, transfer_reference, "
            "recorded_by_tenant_user_id, created_at) "
            "VALUES (:id, :tenant_id, :amount, :currency, :paid_at, :status, "
            ":record_type, :payout_id, :payment_method, :transfer_reference, "
            ":recorded_by_tenant_user_id, :created_at)"
        ),
        values,
    )
    await session.flush()
    return values


async def _run_preflight():
    async with engine.begin() as conn:
        await conn.run_sync(MIGRATION.run_preflight)


def test_payout_payment_model_contract():
    assert PayoutPayment.__tablename__ == "payout_payments"

    amount = PayoutPayment.__table__.c.amount
    assert type(amount.type) is sa.Numeric
    assert amount.type.precision == 20
    assert amount.type.scale == 2

    payout_id = PayoutPayment.__table__.c.payout_id
    assert payout_id.nullable is False
    assert any(
        isinstance(constraint, sa.UniqueConstraint)
        and [column.name for column in constraint.columns] == ["payout_id"]
        for constraint in PayoutPayment.__table__.constraints
    )

    assert PayoutPayment.__table__.c.transfer_reference.nullable is False
    assert PayoutPayment.__table__.c.recorded_by_tenant_user_id.nullable is False

    paid_at = PayoutPayment.__table__.c.paid_at
    assert isinstance(paid_at.type, sa.DateTime)
    assert paid_at.type.timezone is True
    assert paid_at.nullable is False


def test_payout_notification_model_contract():
    assert PayoutNotification.__tablename__ == "payout_notifications"

    payout_id = PayoutNotification.__table__.c.payout_id
    assert payout_id.nullable is False
    assert any(
        isinstance(constraint, sa.UniqueConstraint)
        and [column.name for column in constraint.columns] == ["payout_id"]
        for constraint in PayoutNotification.__table__.constraints
    )

    assert "ck_payout_notifications_status" in {
        constraint.name for constraint in PayoutNotification.__table__.constraints
    }
    assert PayoutNotification.__table__.c.attempt_count.default.arg == 0
    assert PayoutNotification.__table__.c.lease_expires_at.nullable is True


def test_payout_status_check_constraint():
    assert "ck_payouts_status" in {
        constraint.name for constraint in Payout.__table__.constraints
    }
    server_default = Payout.__table__.c.status.server_default
    assert server_default is not None
    assert "pending_approval" in str(server_default.arg)


def test_payout_payment_migration_follows_commission_availability_head():
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_revision("f9a0b1c2d3e4").down_revision == "e8f9a0b1c2d3"
    assert script.get_revision("a1b2c3d4e5f6").down_revision == "f9a0b1c2d3e4"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field",
    [
        "payout_id",
        "transfer_reference",
        "payment_method",
        "paid_at",
        "recorded_by_tenant_user_id",
        "currency",
    ],
)
async def test_preflight_rejects_affiliate_payout_record_missing_field(field):
    async with _legacy_payment_records_table():
        async with async_session() as session:
            record = await _create_affiliate_payout_record(session)
            record_id = record["id"]
            await session.commit()

        async with async_session() as session:
            await session.execute(
                sa.text(
                    f"UPDATE payment_records SET {field} = NULL WHERE id = :id"
                ),
                {"id": record_id},
            )
            await session.commit()

        with pytest.raises(RuntimeError, match="affiliate_payout"):
            await _run_preflight()


@pytest.mark.asyncio
async def test_preflight_rejects_unknown_payment_record_type():
    async with _legacy_payment_records_table():
        async with async_session() as session:
            await _create_affiliate_payout_record(
                session, record_type="legacy_check"
            )
            await session.commit()

        with pytest.raises(RuntimeError, match="record_type"):
            await _run_preflight()


@pytest.mark.asyncio
async def test_preflight_accepts_clean_payment_records():
    async with _legacy_payment_records_table():
        async with async_session() as session:
            await _create_affiliate_payout_record(session)
            await session.commit()

        await _run_preflight()


@pytest.mark.asyncio
async def test_upgrade_creates_tables_and_copies_affiliate_payout_records():
    database = await _create_disposable_database()
    try:
        base = _run_alembic(database, "upgrade", "e8f9a0b1c2d3")
        assert base.returncode == 0, base.stderr + base.stdout

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            ids = await _insert_org(conn)
            payout_ids = [uuid.uuid4(), uuid.uuid4()]
            record_ids = [uuid.uuid4(), uuid.uuid4()]
            for payout_id in payout_ids:
                await _insert_payout(conn, ids, "paid", id=payout_id)
            paid_at = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
            for index, (record_id, payout_id) in enumerate(
                zip(record_ids, payout_ids)
            ):
                await _insert_payment_record(
                    conn,
                    ids,
                    "affiliate_payout",
                    id=record_id,
                    amount=Decimal("10.00") + index,
                    paid_at=paid_at,
                    created_at=paid_at,
                    payout_id=payout_id,
                    payment_method="paypal",
                    transfer_reference=f"txn-{index}",
                    recorded_by_tenant_user_id=ids["user"],
                )
            await _insert_payment_record(
                conn,
                ids,
                "incoming_payment",
                tenant_payment_id="incoming-1",
                amount=Decimal("99.00"),
            )
        finally:
            await conn.close()

        upgrade = _run_alembic(database, "upgrade", "f9a0b1c2d3e4")
        assert upgrade.returncode == 0, upgrade.stderr + upgrade.stdout

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            tables = await conn.fetch(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "AND table_name IN ('payout_payments', 'payout_notifications')"
            )
            assert {row["table_name"] for row in tables} == {
                "payout_payments",
                "payout_notifications",
            }

            unique_constraints = await conn.fetch(
                "SELECT conrelid::regclass::text AS table_name "
                "FROM pg_constraint "
                "WHERE contype = 'u' AND conname IN "
                "('uq_payout_payments_payout_id', 'uq_payout_notifications_payout_id')"
            )
            assert {row["table_name"] for row in unique_constraints} == {
                "payout_payments",
                "payout_notifications",
            }

            amount = await conn.fetchrow(
                "SELECT data_type, numeric_precision, numeric_scale "
                "FROM information_schema.columns "
                "WHERE table_name = 'payout_payments' AND column_name = 'amount'"
            )
            assert amount["data_type"] == "numeric"
            assert amount["numeric_precision"] == 20
            assert amount["numeric_scale"] == 2

            status_check = await conn.fetchval(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_payouts_status'"
            )
            assert status_check is not None
            for status in ("pending_approval", "approved", "rejected", "paid"):
                assert status in status_check

            notification_check = await conn.fetchval(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_payout_notifications_status'"
            )
            assert notification_check is not None
            for status in ("pending", "sending", "sent", "failed"):
                assert status in notification_check

            copied = await conn.fetch(
                "SELECT id, payout_id, payment_method, transfer_reference, "
                "recorded_by_tenant_user_id, amount, currency, paid_at "
                "FROM payout_payments ORDER BY transfer_reference"
            )
            assert len(copied) == 2
            for index, row in enumerate(copied):
                assert row["id"] == record_ids[index]
                assert row["payout_id"] == payout_ids[index]
                assert row["payment_method"] == "paypal"
                assert row["transfer_reference"] == f"txn-{index}"
                assert row["recorded_by_tenant_user_id"] == ids["user"]
                assert row["amount"] == Decimal("10.00") + index
                assert row["currency"] == "USD"
                assert row["paid_at"] == paid_at

            remaining = await conn.fetchval(
                "SELECT COUNT(*) FROM payment_records "
                "WHERE record_type = 'affiliate_payout'"
            )
            assert remaining == 2
            incoming = await conn.fetchval(
                "SELECT COUNT(*) FROM payment_records "
                "WHERE record_type = 'incoming_payment'"
            )
            assert incoming == 1

            default = await conn.fetchval(
                "SELECT column_default FROM information_schema.columns "
                "WHERE table_name = 'payouts' AND column_name = 'status'"
            )
            assert default == "'pending_approval'::character varying"
        finally:
            await conn.close()
    finally:
        await _drop_disposable_database(database)


@pytest.mark.asyncio
async def test_upgrade_aborts_before_ddl_when_payout_record_is_incomplete():
    database = await _create_disposable_database()
    try:
        base = _run_alembic(database, "upgrade", "e8f9a0b1c2d3")
        assert base.returncode == 0, base.stderr + base.stdout

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            ids = await _insert_org(conn)
            payout_id = await _insert_payout(conn, ids, "paid")
            await _insert_payment_record(
                conn,
                ids,
                "affiliate_payout",
                amount=Decimal("10.00"),
                payout_id=payout_id,
                payment_method="paypal",
            )
        finally:
            await conn.close()

        upgrade = _run_alembic(database, "upgrade", "head")
        assert upgrade.returncode != 0

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            tables = await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' "
                "AND table_name IN ('payout_payments', 'payout_notifications')"
            )
            assert tables == 0
            version = await conn.fetchval("SELECT version_num FROM alembic_version")
            assert version == "e8f9a0b1c2d3"
        finally:
            await conn.close()
    finally:
        await _drop_disposable_database(database)


@pytest.mark.asyncio
async def test_retire_aborts_on_incoming_row_and_preserves_table():
    """An incoming_payment row is merchant history nobody else holds; the
    contract migration must refuse to run and leave the table intact."""
    database = await _create_disposable_database()
    try:
        base = _run_alembic(database, "upgrade", "f9a0b1c2d3e4")
        assert base.returncode == 0, base.stderr + base.stdout

        record_id = uuid.uuid4()
        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            ids = await _insert_org(conn)
            await _insert_payment_record(
                conn,
                ids,
                "incoming_payment",
                id=record_id,
                tenant_payment_id="incoming-1",
                amount=Decimal("99.00"),
            )
        finally:
            await conn.close()

        upgrade = _run_alembic(database, "upgrade", "head")
        assert upgrade.returncode != 0
        assert "incoming_payment" in upgrade.stderr

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            assert await _alembic_version(database) == "f9a0b1c2d3e4"
            row = await conn.fetchrow(
                "SELECT id, tenant_payment_id, record_type "
                "FROM payment_records WHERE id = $1",
                record_id,
            )
            assert row["tenant_payment_id"] == "incoming-1"
            assert row["record_type"] == "incoming_payment"
        finally:
            await conn.close()
    finally:
        await _drop_disposable_database(database)


@pytest.mark.asyncio
async def test_retire_aborts_on_sale_event_missing_good_date():
    database = await _create_disposable_database()
    try:
        base = _run_alembic(database, "upgrade", "f9a0b1c2d3e4")
        assert base.returncode == 0, base.stderr + base.stdout

        event_id = uuid.uuid4()
        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            ids = await _insert_org(conn)
            await conn.execute(
                "INSERT INTO events (id, event_id, type, tenant_id) "
                "VALUES ($1, $2, 'sale', $3)",
                event_id,
                f"sale-missing-{uuid.uuid4()}",
                ids["tenant"],
            )
        finally:
            await conn.close()

        upgrade = _run_alembic(database, "upgrade", "head")
        assert upgrade.returncode != 0

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            assert await _alembic_version(database) == "f9a0b1c2d3e4"
            # payment_records still exists — the abort happened before DDL.
            assert await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'payment_records'"
            ) == 1
            assert await conn.fetchval(
                "SELECT COUNT(*) FROM events WHERE id = $1", event_id
            ) == 1
        finally:
            await conn.close()
    finally:
        await _drop_disposable_database(database)


@pytest.mark.asyncio
async def test_retire_drops_payment_records_and_keeps_copied_payment():
    database = await _create_disposable_database()
    try:
        base = _run_alembic(database, "upgrade", "e8f9a0b1c2d3")
        assert base.returncode == 0, base.stderr + base.stdout

        record_id = uuid.uuid4()
        payout_id = uuid.uuid4()
        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            ids = await _insert_org(conn)
            await _insert_payout(conn, ids, "paid", id=payout_id)
            paid_at = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
            await _insert_payment_record(
                conn,
                ids,
                "affiliate_payout",
                id=record_id,
                amount=Decimal("42.50"),
                paid_at=paid_at,
                created_at=paid_at,
                payout_id=payout_id,
                payment_method="paypal",
                transfer_reference="txn-retire",
                recorded_by_tenant_user_id=ids["user"],
            )
        finally:
            await conn.close()

        # The expand revision copies the row; the contract revision retires
        # the table while the copy survives.
        expand = _run_alembic(database, "upgrade", "f9a0b1c2d3e4")
        assert expand.returncode == 0, expand.stderr + expand.stdout
        upgrade = _run_alembic(database, "upgrade", "head")
        assert upgrade.returncode == 0, upgrade.stderr + upgrade.stdout

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            assert await _alembic_version(database) == "a1b2c3d4e5f6"
            assert await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'payment_records'"
            ) == 0

            payment = await conn.fetchrow(
                "SELECT id, payout_id, amount, currency, payment_method, "
                "transfer_reference, paid_at, recorded_by_tenant_user_id "
                "FROM payout_payments WHERE payout_id = $1",
                payout_id,
            )
            assert payment["id"] == record_id
            assert payment["amount"] == Decimal("42.50")
            assert payment["currency"] == "USD"
            assert payment["payment_method"] == "paypal"
            assert payment["transfer_reference"] == "txn-retire"
            assert payment["paid_at"] == paid_at
            assert payment["recorded_by_tenant_user_id"] == ids["user"]

            dropped_columns = await conn.fetch(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND ("
                "(table_name = 'commissions' AND column_name = 'available_on') OR "
                "(table_name = 'payouts' AND column_name = 'paypal_batch_id'))"
            )
            assert dropped_columns == []

            sale_check = await conn.fetchval(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_events_sale_payment_context'"
            )
            assert sale_check is not None
            assert "good_date" in sale_check
            assert "payment_record_id" in sale_check

            assert await conn.fetchval(
                "SELECT COUNT(*) FROM pg_indexes "
                "WHERE schemaname = 'public' "
                "AND indexname = 'ix_payouts_affiliate_requested_at'"
            ) == 1
        finally:
            await conn.close()
    finally:
        await _drop_disposable_database(database)


@pytest.mark.asyncio
async def test_retire_recopies_payout_record_written_after_expand():
    """A payment_records row written by old code after f9a0b1c2d3e4 ran must
    still reach payout_payments before the table is dropped."""
    database = await _create_disposable_database()
    try:
        base = _run_alembic(database, "upgrade", "f9a0b1c2d3e4")
        assert base.returncode == 0, base.stderr + base.stdout

        record_id = uuid.uuid4()
        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            ids = await _insert_org(conn)
            payout_id = await _insert_payout(conn, ids, "paid")
            paid_at = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
            await _insert_payment_record(
                conn,
                ids,
                "affiliate_payout",
                id=record_id,
                amount=Decimal("17.25"),
                paid_at=paid_at,
                created_at=paid_at,
                payout_id=payout_id,
                payment_method="paypal",
                transfer_reference="txn-late",
                recorded_by_tenant_user_id=ids["user"],
            )
        finally:
            await conn.close()

        upgrade = _run_alembic(database, "upgrade", "head")
        assert upgrade.returncode == 0, upgrade.stderr + upgrade.stdout

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            assert await _alembic_version(database) == "a1b2c3d4e5f6"
            assert await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'payment_records'"
            ) == 0
            payment = await conn.fetchrow(
                "SELECT id, amount, transfer_reference FROM payout_payments "
                "WHERE payout_id = $1",
                payout_id,
            )
            assert payment["id"] == record_id
            assert payment["amount"] == Decimal("17.25")
            assert payment["transfer_reference"] == "txn-late"
        finally:
            await conn.close()
    finally:
        await _drop_disposable_database(database)


@pytest.mark.asyncio
async def test_retire_aborts_when_copied_payment_diverges():
    """If a payout_payments row exists but does not match the legacy record,
    the copy is not trustworthy and retirement must stop."""
    database = await _create_disposable_database()
    try:
        base = _run_alembic(database, "upgrade", "f9a0b1c2d3e4")
        assert base.returncode == 0, base.stderr + base.stdout

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            ids = await _insert_org(conn)
            payout_id = await _insert_payout(conn, ids, "paid")
            paid_at = datetime(2026, 2, 2, 12, 0, tzinfo=timezone.utc)
            await _insert_payment_record(
                conn,
                ids,
                "affiliate_payout",
                amount=Decimal("17.25"),
                paid_at=paid_at,
                created_at=paid_at,
                payout_id=payout_id,
                payment_method="paypal",
                transfer_reference="txn-legacy",
                recorded_by_tenant_user_id=ids["user"],
            )
            # Same payout_id, diverging details: ON CONFLICT skips the insert
            # and the verification must catch the mismatch.
            await conn.execute(
                "INSERT INTO payout_payments "
                "(id, payout_id, amount, currency, payment_method, "
                "transfer_reference, paid_at, recorded_by_tenant_user_id, "
                "created_at) "
                "VALUES ($1, $2, 17.25, 'USD', 'paypal', 'txn-different', "
                "$3, $4, now())",
                uuid.uuid4(),
                payout_id,
                paid_at,
                ids["user"],
            )
        finally:
            await conn.close()

        upgrade = _run_alembic(database, "upgrade", "head")
        assert upgrade.returncode != 0

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            assert await _alembic_version(database) == "f9a0b1c2d3e4"
            assert await conn.fetchval(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'payment_records'"
            ) == 1
        finally:
            await conn.close()
    finally:
        await _drop_disposable_database(database)


@pytest.mark.asyncio
async def test_retire_reconciles_reservations_and_matures_due_commissions():
    """Deploy-window leftovers are normalized before the schema shrinks:
    stale active links on closed payouts are released, links to in-flight
    payouts become active reservations, and due unreserved pending
    commissions are promoted."""
    database = await _create_disposable_database()
    try:
        base = _run_alembic(database, "upgrade", "f9a0b1c2d3e4")
        assert base.returncode == 0, base.stderr + base.stdout

        due_at = datetime(2026, 1, 15, tzinfo=timezone.utc)
        future_at = datetime(2999, 1, 15, tzinfo=timezone.utc)
        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            ids = await _insert_org(conn)

            # Stale reservation: link still active although the payout was
            # rejected by old code that did not know is_active.
            stale_event = await _insert_sale_event(conn, ids, "stale")
            stale_commission = await _insert_commission(
                conn, ids, stale_event, "pending", available_at=due_at
            )
            rejected_payout = await _insert_payout(conn, ids, "rejected")
            stale_link = await _insert_payout_commission(
                conn, rejected_payout, stale_commission, is_active=True
            )

            # Stale reserved row behind a paid payout: mirrors
            # confirm_payout_payment settlement.
            paid_event = await _insert_sale_event(conn, ids, "paid")
            paid_commission = await _insert_commission(
                conn, ids, paid_event, "reserved"
            )
            paid_payout = await _insert_payout(conn, ids, "paid")
            paid_link = await _insert_payout_commission(
                conn, paid_payout, paid_commission, is_active=True
            )

            # Legacy reservation: in-flight payout link without is_active.
            inflight_event = await _insert_sale_event(conn, ids, "inflight")
            inflight_commission = await _insert_commission(
                conn, ids, inflight_event, "pending", available_at=due_at
            )
            inflight_payout = await _insert_payout(conn, ids, "pending_approval")
            inflight_link = await _insert_payout_commission(
                conn, inflight_payout, inflight_commission, is_active=False
            )

            # Due and future pending commissions with no link at all.
            due_event = await _insert_sale_event(conn, ids, "due")
            due_commission = await _insert_commission(
                conn, ids, due_event, "pending", available_at=due_at
            )
            future_event = await _insert_sale_event(conn, ids, "future")
            future_commission = await _insert_commission(
                conn, ids, future_event, "pending", available_at=future_at
            )
        finally:
            await conn.close()

        upgrade = _run_alembic(database, "upgrade", "head")
        assert upgrade.returncode == 0, upgrade.stderr + upgrade.stdout

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            assert await _alembic_version(database) == "a1b2c3d4e5f6"

            async def _state(link_id, commission_id):
                link_active = await conn.fetchval(
                    "SELECT is_active FROM payout_commissions WHERE id = $1",
                    link_id,
                )
                status = await conn.fetchval(
                    "SELECT status FROM commissions WHERE id = $1",
                    commission_id,
                )
                return link_active, status

            # Rejected payout: stale link released, due commission promoted.
            assert await _state(stale_link, stale_commission) == (
                False,
                "available",
            )
            # Paid payout: stale link released, commission settled as paid.
            assert await _state(paid_link, paid_commission) == (
                False,
                "paid",
            )
            # In-flight payout: link activated, commission reserved.
            assert await _state(inflight_link, inflight_commission) == (
                True,
                "reserved",
            )
            # Unlinked commissions: due promoted, future stays pending.
            assert (
                await conn.fetchval(
                    "SELECT status FROM commissions WHERE id = $1",
                    due_commission,
                )
                == "available"
            )
            assert (
                await conn.fetchval(
                    "SELECT status FROM commissions WHERE id = $1",
                    future_commission,
                )
                == "pending"
            )
        finally:
            await conn.close()
    finally:
        await _drop_disposable_database(database)


@pytest.mark.asyncio
async def test_retire_downgrade_refuses_when_payout_data_exists():
    database = await _create_disposable_database()
    try:
        base = _run_alembic(database, "upgrade", "head")
        assert base.returncode == 0, base.stderr + base.stdout

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            ids = await _insert_org(conn)
            event_id = await _insert_sale_event(conn, ids, "downgrade")
            await _insert_commission(conn, ids, event_id, "pending")
        finally:
            await conn.close()

        downgrade = _run_alembic(database, "downgrade", "f9a0b1c2d3e4")
        assert downgrade.returncode != 0
        assert await _alembic_version(database) == "a1b2c3d4e5f6"
    finally:
        await _drop_disposable_database(database)


@pytest.mark.asyncio
async def test_retire_downgrade_restores_empty_legacy_structures():
    database = await _create_disposable_database()
    try:
        base = _run_alembic(database, "upgrade", "head")
        assert base.returncode == 0, base.stderr + base.stdout

        downgrade = _run_alembic(database, "downgrade", "f9a0b1c2d3e4")
        assert downgrade.returncode == 0, downgrade.stderr + downgrade.stdout

        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            assert await _alembic_version(database) == "f9a0b1c2d3e4"
            assert await conn.fetchval(
                "SELECT COUNT(*) FROM payment_records"
            ) == 0
            restored_columns = await conn.fetch(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND ("
                "(table_name = 'commissions' AND column_name = 'available_on') OR "
                "(table_name = 'payouts' AND column_name = 'paypal_batch_id'))"
            )
            assert {tuple(row) for row in restored_columns} == {
                ("commissions", "available_on"),
                ("payouts", "paypal_batch_id"),
            }
            assert await conn.fetchval(
                "SELECT COUNT(*) FROM pg_constraint "
                "WHERE conname = 'ck_events_sale_payment_context'"
            ) == 0
            assert await conn.fetchval(
                "SELECT COUNT(*) FROM pg_indexes "
                "WHERE schemaname = 'public' "
                "AND indexname = 'ix_payouts_affiliate_requested_at'"
            ) == 0
        finally:
            await conn.close()
    finally:
        await _drop_disposable_database(database)
