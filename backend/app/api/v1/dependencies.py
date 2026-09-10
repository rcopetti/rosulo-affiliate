import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.db.models import Affiliate, AffiliateAccount, Tenant
from app.core.security import get_token_subject, verify_api_key

bearer_scheme = HTTPBearer(auto_error=False)


async def get_tenant(
    x_api_key: Annotated[str, Header(alias="X-API-Key")],
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    result = await db.execute(select(Tenant))
    for tenant in result.scalars().all():
        if verify_api_key(x_api_key, tenant.api_key_hash):
            return tenant
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


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
        select(AffiliateAccount).where(AffiliateAccount.id == uuid.UUID(subject))
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
