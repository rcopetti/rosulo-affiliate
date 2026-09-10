from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import TenantUser
from app.schemas.tenant_user import TenantUserCreate


async def create_tenant_user(
    db: AsyncSession, tenant_id, data: TenantUserCreate
) -> TenantUser:
    existing = await db.execute(
        select(TenantUser).where(
            TenantUser.tenant_id == tenant_id,
            TenantUser.email == data.email,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("Email already registered for this tenant")
    user = TenantUser(
        tenant_id=tenant_id,
        email=data.email,
        password_hash=hash_password(data.password),
        name=data.name,
        role=data.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_tenant_user(db: AsyncSession, email: str, password: str) -> TenantUser:
    result = await db.execute(
        select(TenantUser)
        .options(selectinload(TenantUser.tenant))
        .where(TenantUser.email == email)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid credentials")
    return user


async def create_token(user: TenantUser) -> str:
    return create_access_token(
        user.id,
        extra={"tenant_id": str(user.tenant_id)},
    )
