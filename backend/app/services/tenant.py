import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_api_key
from app.db.models import Tenant
from app.schemas.tenant import TenantCreate


async def create_tenant(db: AsyncSession, data: TenantCreate, raw_api_key: str) -> Tenant:
    tenant = Tenant(name=data.name, api_key_hash=hash_api_key(raw_api_key))
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return tenant


async def get_tenant_by_id(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant | None:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    return result.scalar_one_or_none()
