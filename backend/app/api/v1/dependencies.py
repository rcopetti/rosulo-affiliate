import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.dependencies import get_db
from app.db.models import Affiliate, AffiliateAccount, AffiliateInvite, Tenant, TenantUser
from app.core.security import decode_token, get_token_subject, verify_api_key

bearer_scheme = HTTPBearer(auto_error=False)


async def get_tenant(
    request: Request,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    # API key authentication (server-to-server integrations)
    if x_api_key:
        result = await db.execute(select(Tenant))
        for tenant in result.scalars().all():
            if verify_api_key(x_api_key, tenant.api_key_hash):
                return tenant
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    # JWT authentication (tenant users or affiliate tokens carrying tenant_id)
    if credentials:
        try:
            payload = decode_token(credentials.credentials)
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

        tenant_id = payload.get("tenant_id")
        if tenant_id:
            tenant = await db.get(Tenant, uuid.UUID(tenant_id))
            if tenant:
                return tenant

        # If no tenant_id, the token may belong to a tenant user; resolve via user.
        user_id = payload.get("sub")
        if user_id:
            user = await db.get(TenantUser, uuid.UUID(user_id))
            if user:
                tenant = await db.get(Tenant, user.tenant_id)
                if tenant:
                    return tenant

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


async def get_tenant_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> TenantUser:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = await db.get(TenantUser, uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def get_current_affiliate_account(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> AffiliateAccount:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    subject = get_token_subject(credentials.credentials)
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(
        select(AffiliateAccount)
        .options(selectinload(AffiliateAccount.documents))
        .where(AffiliateAccount.id == uuid.UUID(subject))
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")
    return account


async def get_current_affiliate(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    x_tenant_id: Annotated[str, Header(alias="X-Tenant-Id")],
    db: AsyncSession = Depends(get_db),
) -> Affiliate:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    subject = get_token_subject(credentials.credentials)
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    account_result = await db.execute(
        select(AffiliateAccount).where(AffiliateAccount.id == uuid.UUID(subject))
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")
    result = await db.execute(
        select(Affiliate).where(
            Affiliate.affiliate_account_id == account.id,
            Affiliate.tenant_id == uuid.UUID(x_tenant_id),
        )
    )
    affiliate = result.scalar_one_or_none()
    if not affiliate:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Affiliate is not linked to this tenant",
        )
    return affiliate
