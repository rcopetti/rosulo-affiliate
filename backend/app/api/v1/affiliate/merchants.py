import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_affiliate_account
from app.db.dependencies import get_db
from app.db.models import Affiliate, AffiliateAccount, Tenant
from app.services import affiliate_account as acct_service
from app.services import affiliate as affiliate_service

router = APIRouter()


@router.get("")
async def list_merchants(
    account: AffiliateAccount = Depends(get_current_affiliate_account),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Affiliate, Tenant)
        .join(Tenant, Affiliate.tenant_id == Tenant.id)
        .where(Affiliate.affiliate_account_id == account.id)
    )
    return [
        {
            "tenant_id": str(t.id),
            "name": t.name,
            "kyc_approved_for_payout": a.kyc_approved_for_payout,
        }
        for a, t in result.all()
    ]


@router.post("/{tenant_id}/join")
async def join_tenant(
    tenant_id: str,
    account: AffiliateAccount = Depends(get_current_affiliate_account),
    db: AsyncSession = Depends(get_db),
):
    from app.services.tenant import get_tenant_by_id

    tenant = await get_tenant_by_id(db, uuid.UUID(tenant_id))
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    existing = await db.execute(
        select(Affiliate).where(
            Affiliate.affiliate_account_id == account.id,
            Affiliate.tenant_id == tenant.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Already linked")
    affiliate = Affiliate(
        affiliate_account_id=account.id,
        tenant_id=tenant.id,
    )
    db.add(affiliate)
    await db.commit()
    await db.refresh(affiliate)
    return {"status": "joined", "affiliate_id": str(affiliate.id)}


@router.post("/{tenant_id}/select")
async def select_tenant(tenant_id: str):
    return {"tenant_id": tenant_id}
