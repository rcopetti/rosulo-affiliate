from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_tenant
from app.db.dependencies import get_db
from app.db.models import Commission, Tenant
from app.schemas.event import EventCreate, EventOut
from app.services import commission as commission_service
from app.services import event as event_service

router = APIRouter()


@router.post("", response_model=EventOut)
async def ingest_event(
    data: EventCreate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import func

    event = await event_service.ingest_event(db, tenant, data)
    commission_count = (
        await db.execute(select(func.count(Commission.id)).where(Commission.event_id == event.id))
    ).scalar()
    if event.type == "sale" and event.affiliate_id and not commission_count:
        from app.db.models import Affiliate

        affiliate = await db.get(Affiliate, event.affiliate_id)
        commission = await commission_service.calculate_from_sale_event(db, event, affiliate)
        if commission:
            await commission_service.mark_available_commissions(db)
    return event
