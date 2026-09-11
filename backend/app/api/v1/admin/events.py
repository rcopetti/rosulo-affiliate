from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_tenant
from app.db.dependencies import get_db
from app.db.models import Event, Tenant
from app.schemas.event import EventOut, PaginatedEvents

router = APIRouter()


@router.get("", response_model=PaginatedEvents)
async def list_events(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    type: str | None = None,
    skip: int = 0,
    limit: int = 20,
):
    filters = [Event.tenant_id == tenant.id]
    if type:
        filters.append(Event.type == type)

    count_query = select(func.count()).select_from(Event).where(*filters)
    total = (await db.execute(count_query)).scalar() or 0

    query = (
        select(Event)
        .where(*filters)
        .order_by(Event.occurred_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    items = list(result.scalars().all())

    return PaginatedEvents(items=items, total=total, skip=skip, limit=limit)
