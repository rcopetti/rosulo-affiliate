from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_affiliate
from app.db.dependencies import get_db
from app.db.models import Affiliate, Commission

router = APIRouter()


@router.get("/balance")
async def get_balance(
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Commission.status, func.sum(Commission.net_amount))
        .where(Commission.affiliate_id == affiliate.id)
        .group_by(Commission.status)
    )
    balance = {"earned": 0, "pending": 0, "available": 0, "paid": 0, "reversed": 0}
    for status, amount in result.all():
        if status in balance:
            balance[status] = float(amount or 0)
    return balance


@router.get("/commissions")
async def list_commissions(
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Commission).where(Commission.affiliate_id == affiliate.id)
    )
    return result.scalars().all()
