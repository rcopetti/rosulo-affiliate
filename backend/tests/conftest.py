import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.security import hash_api_key, hash_password
from app.db.base import Base
from app.db.models import Tenant, TenantUser
from app.db.session import async_session, engine
from app.main import app


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
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
