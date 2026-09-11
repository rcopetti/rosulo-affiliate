from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_tenant
from app.db.dependencies import get_db
from app.db.models import Tenant
from app.schemas.dashboard import TenantDashboardOut
from app.services import dashboard as dashboard_service

router = APIRouter()


@router.get("", response_model=TenantDashboardOut)
async def admin_dashboard(
    tenant: Tenant = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    return await dashboard_service.tenant_dashboard(db, tenant.id)
