import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.dependencies import get_db
from app.schemas.auth import TenantLogin, TenantRegister, TenantRegisterResponse
from app.schemas.tenant import TenantCreate
from app.schemas.tenant_user import TenantUserCreate, TenantUserOut
from app.schemas.tenant import TenantOut
from app.services import tenant as tenant_service
from app.services import tenant_user as tenant_user_service

router = APIRouter()


class TenantAuthResponse(TenantUserOut):
    token: str
    tenant: TenantOut


@router.post("/tenant/login", response_model=TenantAuthResponse)
async def login(data: TenantLogin, db: AsyncSession = Depends(get_db)):
    try:
        user = await tenant_user_service.authenticate_tenant_user(
            db, data.email, data.password
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    token = await tenant_user_service.create_token(user)
    return {
        "token": token,
        "id": user.id,
        "tenant_id": user.tenant_id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "tenant": user.tenant,
    }


@router.post("/tenant/register", response_model=TenantRegisterResponse)
async def register(data: TenantRegister, db: AsyncSession = Depends(get_db)):
    try:
        raw_api_key = secrets.token_urlsafe(32)
        tenant = await tenant_service.create_tenant(
            db, TenantCreate(name=data.tenant_name), raw_api_key
        )
        user = await tenant_user_service.create_tenant_user(
            db,
            tenant.id,
            TenantUserCreate(
                email=data.email,
                password=data.password,
                name=data.admin_name or "Admin",
            ),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    token = create_access_token(str(user.id), extra={"tenant_id": str(tenant.id)})
    return {
        "token": token,
        "tenant": tenant,
        "user": user,
        "api_key": raw_api_key,
    }
