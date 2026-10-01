from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_affiliate
from app.db.dependencies import get_db
from app.db.models import Affiliate, Commission
from app.schemas.dashboard import BalanceOut
from app.services.balance import add_legacy_balance_fields, get_balances

router = APIRouter()


@router.get("/balance", response_model=BalanceOut)
async def get_balance(
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    balances = await get_balances(db, affiliate.id)
    return add_legacy_balance_fields(balances)


@router.get("/commissions")
async def list_commissions(
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Commission).where(Commission.affiliate_id == affiliate.id)
    )
    return result.scalars().all()
