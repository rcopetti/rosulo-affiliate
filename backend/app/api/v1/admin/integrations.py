import secrets

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_tenant
from app.core.security import hash_api_key
from app.db.dependencies import get_db
from app.db.models import Tenant

router = APIRouter()


@router.post("/api-key")
async def rotate_api_key(
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    raw = "rak_" + secrets.token_urlsafe(32)
    tenant.api_key_hash = hash_api_key(raw)
    await db.commit()
    await db.refresh(tenant)
    return {"api_key": raw, "tenant_id": str(tenant.id)}
