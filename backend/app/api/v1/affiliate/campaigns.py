import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_affiliate
from app.db.dependencies import get_db
from app.db.models import Affiliate, Campaign
from app.schemas.campaign import CampaignCreate, CampaignOut, CampaignUpdate
from app.services import campaign as campaign_service

router = APIRouter()


@router.post("", response_model=CampaignOut)
async def create_campaign(
    data: CampaignCreate,
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_service.create_campaign(db, affiliate, data)


@router.get("", response_model=list[CampaignOut])
async def list_campaigns(
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_service.list_campaigns(db, affiliate)


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: str,
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    return await campaign_service.get_campaign(db, uuid.UUID(campaign_id), affiliate)


@router.patch("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: str,
    data: CampaignUpdate,
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    campaign = await campaign_service.get_campaign(db, uuid.UUID(campaign_id), affiliate)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return await campaign_service.update_campaign(db, campaign, data)
