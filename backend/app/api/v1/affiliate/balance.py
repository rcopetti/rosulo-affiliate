from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_affiliate
from app.db.dependencies import get_db
from app.db.models import Affiliate
from app.schemas.commission import CommissionOut
from app.schemas.dashboard import BalanceOut
from app.services.balance import (
    add_legacy_balance_fields,
    get_balances,
    list_commissions_with_logical_status,
)

router = APIRouter()


@router.get("/balance", response_model=BalanceOut)
async def get_balance(
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    balances = await get_balances(db, affiliate.id)
    return add_legacy_balance_fields(balances)


@router.get("/commissions", response_model=list[CommissionOut])
async def list_commissions(
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    rows = await list_commissions_with_logical_status(db, affiliate.id)
    return [
        CommissionOut.model_validate(commission).model_copy(
            update={"status": logical_status}
        )
        for commission, logical_status in rows
    ]
