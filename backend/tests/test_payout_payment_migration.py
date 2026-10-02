import importlib.util
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
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
    PaymentRecord,
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
    }
    values.update(overrides)
    record = PaymentRecord(**values)
    session.add(record)
    await session.flush()
    return record


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

    assert script.get_current_head() == "f9a0b1c2d3e4"
    assert script.get_revision("f9a0b1c2d3e4").down_revision == "e8f9a0b1c2d3"


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
    async with async_session() as session:
        record = await _create_affiliate_payout_record(session)
        record_id = record.id
        await session.commit()

    async with async_session() as session:
        await session.execute(
            sa.update(PaymentRecord)
            .where(PaymentRecord.id == record_id)
            .values(**{field: None})
        )
        await session.commit()

    with pytest.raises(RuntimeError, match="affiliate_payout"):
        await _run_preflight()


@pytest.mark.asyncio
async def test_preflight_rejects_unknown_payment_record_type():
    async with async_session() as session:
        await _create_affiliate_payout_record(session, record_type="legacy_check")
        await session.commit()

    with pytest.raises(RuntimeError, match="record_type"):
        await _run_preflight()


@pytest.mark.asyncio
async def test_preflight_accepts_clean_payment_records():
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

        ids = {key: uuid.uuid4() for key in ("tenant", "user", "account", "affiliate")}
        payout_ids = [uuid.uuid4(), uuid.uuid4()]
        record_ids = [uuid.uuid4(), uuid.uuid4()]
        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            await conn.execute(
                "INSERT INTO tenants (id, name, api_key_hash) VALUES ($1, 'acme', 'hash')",
                ids["tenant"],
            )
            await conn.execute(
                "INSERT INTO tenant_users (id, tenant_id, email, password_hash, role) "
                "VALUES ($1, $2, 'admin@example.com', 'hash', 'admin')",
                ids["user"],
                ids["tenant"],
            )
            await conn.execute(
                "INSERT INTO affiliate_accounts "
                "(id, email, password_hash, name, country, tax_status) "
                "VALUES ($1, 'affiliate@example.com', 'hash', 'Affiliate', 'US', 'us_person')",
                ids["account"],
            )
            await conn.execute(
                "INSERT INTO affiliates (id, affiliate_account_id, tenant_id) "
                "VALUES ($1, $2, $3)",
                ids["affiliate"],
                ids["account"],
                ids["tenant"],
            )
            for payout_id in payout_ids:
                await conn.execute(
                    "INSERT INTO payouts (id, affiliate_id, tenant_id, status, currency) "
                    "VALUES ($1, $2, $3, 'paid', 'USD')",
                    payout_id,
                    ids["affiliate"],
                    ids["tenant"],
                )
            paid_at = datetime(2026, 2, 1, 12, 0, tzinfo=timezone.utc)
            for index, (record_id, payout_id) in enumerate(
                zip(record_ids, payout_ids)
            ):
                await conn.execute(
                    "INSERT INTO payment_records "
                    "(id, tenant_id, amount, currency, paid_at, status, record_type, "
                    "payout_id, payment_method, transfer_reference, "
                    "recorded_by_tenant_user_id, created_at) "
                    "VALUES ($1, $2, $3, 'USD', $4, 'paid', 'affiliate_payout', "
                    "$5, 'paypal', $6, $7, $4)",
                    record_id,
                    ids["tenant"],
                    Decimal("10.00") + index,
                    paid_at,
                    payout_id,
                    f"txn-{index}",
                    ids["user"],
                )
            await conn.execute(
                "INSERT INTO payment_records "
                "(id, tenant_id, tenant_payment_id, amount, currency, paid_at, "
                "status, record_type, created_at) "
                "VALUES ($1, $2, 'incoming-1', 99.00, 'USD', $3, 'paid', "
                "'incoming_payment', $3)",
                uuid.uuid4(),
                ids["tenant"],
                paid_at,
            )
        finally:
            await conn.close()

        upgrade = _run_alembic(database, "upgrade", "head")
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

        ids = {key: uuid.uuid4() for key in ("tenant", "account", "affiliate")}
        payout_id = uuid.uuid4()
        conn = await asyncpg.connect(_disposable_dsn(database))
        try:
            await conn.execute(
                "INSERT INTO tenants (id, name, api_key_hash) VALUES ($1, 'acme', 'hash')",
                ids["tenant"],
            )
            await conn.execute(
                "INSERT INTO affiliate_accounts "
                "(id, email, password_hash, name, country, tax_status) "
                "VALUES ($1, 'affiliate@example.com', 'hash', 'Affiliate', 'US', 'us_person')",
                ids["account"],
            )
            await conn.execute(
                "INSERT INTO affiliates (id, affiliate_account_id, tenant_id) "
                "VALUES ($1, $2, $3)",
                ids["affiliate"],
                ids["account"],
                ids["tenant"],
            )
            await conn.execute(
                "INSERT INTO payouts (id, affiliate_id, tenant_id, status, currency) "
                "VALUES ($1, $2, $3, 'paid', 'USD')",
                payout_id,
                ids["affiliate"],
                ids["tenant"],
            )
            await conn.execute(
                "INSERT INTO payment_records "
                "(id, tenant_id, amount, currency, paid_at, status, record_type, "
                "payout_id, payment_method, created_at) "
                "VALUES ($1, $2, 10.00, 'USD', now(), 'paid', 'affiliate_payout', "
                "$3, 'paypal', now())",
                uuid.uuid4(),
                ids["tenant"],
                payout_id,
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
