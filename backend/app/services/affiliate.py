import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import Affiliate, Tenant


def _affiliate_out(affiliate: Affiliate) -> dict:
    return {
        "id": affiliate.id,
        "tenant_id": affiliate.tenant_id,
        "affiliate_account_id": affiliate.affiliate_account_id,
        "email": affiliate.account.email,
        "name": affiliate.account.name,
        "kyc_approved_for_payout": affiliate.kyc_approved_for_payout,
    }


async def list_affiliates(db: AsyncSession, tenant: Tenant):
    result = await db.execute(
        select(Affiliate)
        .options(selectinload(Affiliate.account))
        .where(Affiliate.tenant_id == tenant.id)
    )
    return [_affiliate_out(a) for a in result.scalars().all()]


async def get_affiliate(db: AsyncSession, affiliate_id: uuid.UUID, tenant: Tenant):
    result = await db.execute(
        select(Affiliate)
        .options(selectinload(Affiliate.account))
        .where(
            Affiliate.id == affiliate_id,
            Affiliate.tenant_id == tenant.id,
        )
    )
    affiliate = result.scalar_one_or_none()
    return _affiliate_out(affiliate) if affiliate else None


async def approve_affiliate_kyc(db: AsyncSession, affiliate_id: uuid.UUID, tenant: Tenant):
    result = await db.execute(
        select(Affiliate).where(
            Affiliate.id == affiliate_id,
            Affiliate.tenant_id == tenant.id,
        )
    )
    affiliate = result.scalar_one_or_none()
    if not affiliate:
        return None
    affiliate.kyc_approved_for_payout = True
    await db.commit()
    await db.refresh(affiliate)
    return await get_affiliate(db, affiliate_id, tenant)


async def reject_affiliate_kyc(db: AsyncSession, affiliate_id: uuid.UUID, tenant: Tenant):
    result = await db.execute(
        select(Affiliate).where(
            Affiliate.id == affiliate_id,
            Affiliate.tenant_id == tenant.id,
        )
    )
    affiliate = result.scalar_one_or_none()
    if not affiliate:
        return None
    affiliate.kyc_approved_for_payout = False
    await db.commit()
    await db.refresh(affiliate)
    return await get_affiliate(db, affiliate_id, tenant)
