from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_tenant
from app.db.dependencies import get_db
from app.db.models import Event, Tenant
from app.schemas.event import EventOut

router = APIRouter()


@router.get("", response_model=list[EventOut])
async def list_events(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
    type: str | None = None,
):
    query = select(Event).where(Event.tenant_id == tenant.id)
    if type:
        query = query.where(Event.type == type)
    result = await db.execute(query)
    return result.scalars().all()
