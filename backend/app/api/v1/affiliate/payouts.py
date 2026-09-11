from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_affiliate
from app.db.dependencies import get_db
from app.db.models import Affiliate, Payout
from app.schemas.payout import PayoutOut, PayoutRequest
from app.services import payout as payout_service

router = APIRouter()


@router.post("/payout-requests", response_model=PayoutOut)
async def request_payout(
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    return await payout_service.request_payout(db, affiliate)


@router.get("/payouts", response_model=list[PayoutOut])
async def list_payouts(
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Payout).where(Payout.affiliate_id == affiliate.id))
    return result.scalars().all()
