import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Affiliate, AffiliateAccount, Tenant
from app.schemas.affiliate import AffiliateCreate


async def list_affiliates(db: AsyncSession, tenant: Tenant):
    result = await db.execute(
        select(Affiliate).where(Affiliate.tenant_id == tenant.id)
    )
    return result.scalars().all()


async def get_affiliate(db: AsyncSession, affiliate_id: uuid.UUID, tenant: Tenant):
    result = await db.execute(
        select(Affiliate).where(
            Affiliate.id == affiliate_id,
            Affiliate.tenant_id == tenant.id,
        )
    )
    return result.scalar_one_or_none()


async def approve_affiliate_kyc(db: AsyncSession, affiliate_id: uuid.UUID, tenant: Tenant):
    affiliate = await get_affiliate(db, affiliate_id, tenant)
    if not affiliate:
        return None
    affiliate.kyc_approved_for_payout = True
    await db.commit()
    await db.refresh(affiliate)
    return affiliate


async def reject_affiliate_kyc(db: AsyncSession, affiliate_id: uuid.UUID, tenant: Tenant):
    affiliate = await get_affiliate(db, affiliate_id, tenant)
    if not affiliate:
        return None
    affiliate.kyc_approved_for_payout = False
    await db.commit()
    await db.refresh(affiliate)
    return affiliate
