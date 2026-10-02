import os
import types
import uuid
from decimal import Decimal

import asyncpg
from sqlalchemy.engine.url import make_url

# Tests must not touch the dev database. Use TEST_DATABASE_URL if provided,
# otherwise append "_test" to the configured database name and create it.
from app.core.config import settings

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

if TEST_DATABASE_URL:
    _TEST_DATABASE_URL = TEST_DATABASE_URL
else:
    _url = make_url(settings.database_url)
    _test_db = f"{_url.database}_test"
    # render_as_string(hide_password=False) — str(URL) masks the password as
    # '***' in SQLAlchemy 2.x, which would break authentication downstream.
    _TEST_DATABASE_URL = _url.set(database=_test_db).render_as_string(hide_password=False)

settings.database_url = _TEST_DATABASE_URL
os.environ["DATABASE_URL"] = _TEST_DATABASE_URL

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.security import hash_api_key, hash_password
from app.db.base import Base
from app.db.models import Commission, Event, Payout, PayoutCommission, Tenant, TenantUser
from app.db.session import async_session, engine
from app.main import app
from app.services.commission import utc_midnight


def _pg_dsn(url):
    password = f":{url.password}" if url.password else ""
    port = f":{url.port}" if url.port else ""
    return f"postgresql://{url.username}{password}@{url.host}{port}/{url.database}"


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    target_url = make_url(engine.url)
    target_dsn = _pg_dsn(target_url)

    # If the test database already exists (e.g. TEST_DATABASE_URL was set), use it.
    db_exists = False
    try:
        conn = await asyncpg.connect(target_dsn)
        await conn.close()
        db_exists = True
    except asyncpg.InvalidCatalogNameError:
        db_exists = False
    except Exception as exc:
        raise RuntimeError(
            f"Could not connect to test database {target_url.database}. "
            "Set TEST_DATABASE_URL to a pre-created test database or ensure the configured credentials are correct."
        ) from exc

    if not db_exists:
        # Create the test database by connecting to the default 'postgres' database.
        admin_url = target_url.set(database="postgres")
        admin_dsn = _pg_dsn(admin_url)
        test_db = target_url.database

        try:
            conn = await asyncpg.connect(admin_dsn)
        except Exception as exc:
            raise RuntimeError(
                f"Could not connect to {admin_url.host}:{admin_url.port} to create the test database. "
                "Set TEST_DATABASE_URL to a pre-created test database or ensure the configured credentials can connect to the 'postgres' database."
            ) from exc
        try:
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", test_db
            )
            if not exists:
                await conn.execute(f'CREATE DATABASE "{test_db}"')
        finally:
            await conn.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture(scope="function")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(scope="function")
async def tenant():
    async with async_session() as db:
        t = Tenant(name="allbum", api_key_hash=hash_api_key("test-api-key"))
        db.add(t)
        await db.commit()
        await db.refresh(t)
        yield t


@pytest_asyncio.fixture(scope="function")
async def tenant_user(tenant):
    async with async_session() as db:
        u = TenantUser(
            tenant_id=tenant.id,
            email="admin@allbum.me",
            password_hash=hash_password("admin123"),
            name="Admin User",
            role="admin",
        )
        db.add(u)
        await db.commit()
        await db.refresh(u)
        yield u


@pytest_asyncio.fixture(scope="function")
async def payout_scenario(client, tenant, tenant_user, monkeypatch):
    """Reusable end-to-end setup: admin login, an invited + accepted affiliate
    with an approved payout document (real payout eligibility), and a campaign.

    Returns a namespace with precise commission helpers:
      - create_commission(good_date, payment_record_id) -> commission id
      - commission_status(commission_id) -> status string
      - add_legacy_active_payout(commission_id, payout_status=..., is_active=...)
      - db_session: async_session callable usable as `async with ... as db`
    """
    admin_login = await client.post(
        "/api/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "payout-scenario@example.com"},
    )
    assert invite.status_code == 200
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/api/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "payout-scenario@example.com",
            "password": "secret123",
            "name": "Payout Scenario Tester",
            "country": "US",
            "tax_status": "us_person",
            "paypal_email": "payout-scenario@example.com",
        },
    )
    assert accept.status_code == 200
    token = accept.json()["token"]

    affiliates = await client.get(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    account_id = accept.json()["account"]["id"]
    affiliate_id = uuid.UUID(
        next(a["id"] for a in affiliates.json() if a["account_id"] == account_id)
    )

    camp = await client.post(
        "/api/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Payout Scenario Camp", "landing_url": "https://allbum.me/ps"},
    )
    assert camp.status_code == 200
    campaign_id = uuid.UUID(camp.json()["id"])

    monkeypatch.setattr(
        "app.services.affiliate_account.put_document",
        lambda document_id, content: f"private/{document_id}",
    )
    affiliate_headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": str(tenant.id),
    }
    uploaded = await client.post(
        "/api/v1/affiliate/documents",
        headers=affiliate_headers,
        data={"type": "W-9"},
        files={"file": ("w9.pdf", b"tax document", "application/pdf")},
    )
    assert uploaded.status_code == 200
    document_id = uploaded.json()["id"]
    reviewed = await client.post(
        f"/api/v1/admin/affiliates/{affiliate_id}/documents/{document_id}/review",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "approved"},
    )
    assert reviewed.status_code == 200

    async def create_commission(
        good_date,
        payment_record_id,
        *,
        status="pending",
        available_at="auto",
        available_on=None,
    ):
        """Insert a sale Event plus a Commission; returns the commission id.

        ``available_at="auto"`` derives UTC midnight from ``good_date``; pass
        ``None`` explicitly to simulate rows written by older app versions
        that left the column null.
        """
        if available_at == "auto":
            available_at = utc_midnight(good_date)
        if available_on is None:
            available_on = good_date
        async with async_session() as db:
            event = Event(
                event_id=f"sale-{payment_record_id}",
                type="sale",
                tenant_id=tenant.id,
                campaign_id=campaign_id,
                affiliate_id=affiliate_id,
                customer_id=f"cust-{payment_record_id}",
                amount=Decimal("100.00"),
                currency="USD",
                payment_sequence=1,
                good_date=good_date,
                payment_record_id=payment_record_id,
            )
            db.add(event)
            await db.flush()
            commission = Commission(
                event_id=event.id,
                affiliate_id=affiliate_id,
                campaign_id=campaign_id,
                gross_amount=Decimal("10.00"),
                withholding_amount=Decimal("0.00"),
                net_amount=Decimal("10.00"),
                currency="USD",
                status=status,
                available_on=available_on,
                available_at=available_at,
            )
            db.add(commission)
            await db.commit()
            return commission.id

    async def commission_status(commission_id):
        async with async_session() as db:
            return await db.scalar(select(Commission.status).where(Commission.id == commission_id))

    async def add_legacy_active_payout(
        commission_id, *, payout_status="pending_approval", is_active=False
    ):
        """Link the commission to a payout the way older app versions did:
        the reservation was expressed only by the parent payout status while
        ``PayoutCommission.is_active`` kept its false default."""
        async with async_session() as db:
            payout = Payout(
                affiliate_id=affiliate_id,
                tenant_id=tenant.id,
                status=payout_status,
                currency="USD",
            )
            db.add(payout)
            await db.flush()
            db.add(
                PayoutCommission(
                    payout_id=payout.id,
                    commission_id=commission_id,
                    amount=Decimal("10.00"),
                    is_active=is_active,
                )
            )
            await db.commit()
            return payout.id

    return types.SimpleNamespace(
        tenant_id=tenant.id,
        affiliate_id=affiliate_id,
        campaign_id=campaign_id,
        admin_token=admin_token,
        affiliate_headers=affiliate_headers,
        db_session=async_session,
        create_commission=create_commission,
        commission_status=commission_status,
        add_legacy_active_payout=add_legacy_active_payout,
    )
