import os

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

from app.core.security import hash_api_key, hash_password
from app.db.base import Base
from app.db.models import Tenant, TenantUser
from app.db.session import async_session, engine
from app.main import app


def _pg_dsn(url):
    password = f":{url.password}" if url.password else ""
    port = f":{url.port}" if url.port else ""
    return f"postgresql://{url.username}{password}@{url.host}{port}/{url.database}"


@pytest_asyncio.fixture(scope="session", autouse=True)
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


@pytest_asyncio.fixture(scope="session")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(scope="session")
async def tenant():
    async with async_session() as db:
        t = Tenant(name="allbum", api_key_hash=hash_api_key("test-api-key"))
        db.add(t)
        await db.commit()
        await db.refresh(t)
        yield t


@pytest_asyncio.fixture(scope="session")
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
