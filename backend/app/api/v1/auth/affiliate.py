from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.dependencies import get_db
from app.db.models import Affiliate, AffiliateAccount, Tenant
from app.schemas.affiliate_account import AffiliateAccountOut
from app.schemas.auth import AffiliateAcceptInvite, AffiliateLogin, AuthResponse
from app.schemas.tenant import TenantOut
from app.services import affiliate_account as acct_service
from app.services import affiliate_invite as invite_service

router = APIRouter()


async def _auth_response(db: AsyncSession, account: AffiliateAccount) -> AuthResponse:
    token = create_access_token(account.id)
    account_out = AffiliateAccountOut.model_validate(account)
    tenant_result = await db.execute(
        select(Tenant).join(Affiliate, Affiliate.tenant_id == Tenant.id).where(
            Affiliate.affiliate_account_id == account.id
        )
    )
    tenants = [TenantOut.model_validate(t) for t in tenant_result.scalars().all()]
    return AuthResponse(token=token, account=account_out, tenants=tenants)


@router.post("/affiliate/login", response_model=AuthResponse)
async def login(data: AffiliateLogin, db: AsyncSession = Depends(get_db)):
    account = await acct_service.authenticate_account(db, data)
    return await _auth_response(db, account)


@router.post("/affiliate/accept-invite", response_model=AuthResponse)
async def accept_invite(data: AffiliateAcceptInvite, db: AsyncSession = Depends(get_db)):
    account, tenant = await invite_service.accept_invite(db, data)
    return await _auth_response(db, account)
