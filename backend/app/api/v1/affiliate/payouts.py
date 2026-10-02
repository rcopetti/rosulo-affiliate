import uuid

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
    data: PayoutRequest,
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    return await payout_service.request_payout(
        db, affiliate, data.currency, data.commission_ids
    )


@router.get("/payouts", response_model=list[PayoutOut])
async def list_payouts(
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Payout)
        .where(Payout.affiliate_id == affiliate.id)
        .options(*payout_service.payout_detail_options())
    )
    return result.scalars().all()


@router.get("/payouts/{payout_id}", response_model=PayoutOut)
async def get_payout(
    payout_id: str,
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    """Payout detail for the authenticated affiliate — the target of the
    payout-paid email deep link. ``get_current_affiliate`` already binds the
    caller to the ``X-Tenant-Id`` tenant; ownership is enforced here, so the
    ``tenant_id`` in the emailed URL stays routing context only."""
    try:
        payout_uuid = uuid.UUID(payout_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Payout not found")
    result = await db.execute(
        select(Payout)
        .where(
            Payout.id == payout_uuid,
            Payout.affiliate_id == affiliate.id,
            Payout.tenant_id == affiliate.tenant_id,
        )
        .options(*payout_service.payout_detail_options())
    )
    payout = result.scalar_one_or_none()
    if not payout:
        # Same 404 for unknown and other-affiliate payouts: existence of a
        # payout belonging to someone else is never revealed.
        raise HTTPException(status_code=404, detail="Payout not found")
    return payout
