from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_affiliate
from app.db.dependencies import get_db
from app.db.models import Affiliate
from app.schemas.dashboard import AffiliateDashboardOut
from app.services import dashboard as dashboard_service

router = APIRouter()


@router.get("", response_model=AffiliateDashboardOut)
async def affiliate_dashboard(
    affiliate: Affiliate = Depends(get_current_affiliate),
    db: AsyncSession = Depends(get_db),
):
    return await dashboard_service.affiliate_dashboard(db, affiliate.id)
