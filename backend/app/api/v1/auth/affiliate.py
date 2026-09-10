from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.db.models import Affiliate, AffiliateAccount, Tenant
from app.schemas.affiliate_account import AffiliateAccountOut
from app.schemas.auth import AffiliateLogin, AffiliateRegister, AuthResponse
from app.schemas.tenant import TenantOut
from app.services import affiliate_account as acct_service

router = APIRouter()


async def _tenants_for_account(db: AsyncSession, account_id) -> list[TenantOut]:
    result = await db.execute(
        select(Tenant)
        .join(Affiliate, Affiliate.tenant_id == Tenant.id)
        .where(Affiliate.affiliate_account_id == account_id)
    )
    return [TenantOut.model_validate(t) for t in result.scalars().all()]


@router.post("/affiliate/register", response_model=AuthResponse)
async def register(data: AffiliateRegister, db: AsyncSession = Depends(get_db)):
    account = await acct_service.register_account(db, data)
    token = await acct_service.authenticate_account(
        db, AffiliateLogin(email=data.email, password=data.password)
    )
    return AuthResponse(
        token=token,
        account=AffiliateAccountOut.model_validate(account),
        tenants=await _tenants_for_account(db, account.id),
    )


@router.post("/affiliate/login", response_model=AuthResponse)
async def login(data: AffiliateLogin, db: AsyncSession = Depends(get_db)):
    token = await acct_service.authenticate_account(db, data)
    result = await db.execute(
        select(AffiliateAccount).where(AffiliateAccount.email == data.email)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return AuthResponse(
        token=token,
        account=AffiliateAccountOut.model_validate(account),
        tenants=await _tenants_for_account(db, account.id),
    )
