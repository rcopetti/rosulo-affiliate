import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Affiliate, Campaign
from app.schemas.campaign import CampaignCreate, CampaignUpdate


def _make_tracking_code() -> str:
    return "ros-" + secrets.token_urlsafe(12)


async def list_campaigns(db: AsyncSession, affiliate: Affiliate):
    result = await db.execute(
        select(Campaign).where(
            Campaign.affiliate_id == affiliate.id,
            Campaign.tenant_id == affiliate.tenant_id,
        )
    )
    return result.scalars().all()


async def get_campaign(db: AsyncSession, campaign_id: uuid.UUID, affiliate: Affiliate):
    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.affiliate_id == affiliate.id,
            Campaign.tenant_id == affiliate.tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def create_campaign(
    db: AsyncSession, affiliate: Affiliate, data: CampaignCreate
) -> Campaign:
    campaign = Campaign(
        affiliate_id=affiliate.id,
        tenant_id=affiliate.tenant_id,
        tracking_code=_make_tracking_code(),
        landing_url=data.landing_url,
        name=data.name,
        active=data.active,
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def update_campaign(
    db: AsyncSession, campaign: Campaign, data: CampaignUpdate
) -> Campaign:
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(campaign, key, value)
    await db.commit()
    await db.refresh(campaign)
    return campaign
