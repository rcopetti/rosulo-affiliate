from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_affiliate_account
from app.db.dependencies import get_db
from app.db.models import AffiliateAccount
from app.schemas.affiliate_account import AffiliateAccountOut, AffiliateAccountUpdate
from app.services import affiliate_account as acct_service

router = APIRouter()


@router.get("/profile", response_model=AffiliateAccountOut)
async def get_profile(
    account: AffiliateAccount = Depends(get_current_affiliate_account),
):
    return account


@router.patch("/profile", response_model=AffiliateAccountOut)
async def update_profile(
    data: AffiliateAccountUpdate,
    account: AffiliateAccount = Depends(get_current_affiliate_account),
    db: AsyncSession = Depends(get_db),
):
    return await acct_service.update_account(db, account, data)
