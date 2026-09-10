from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.schemas.auth import TenantLogin
from app.schemas.tenant import TenantOut
from app.schemas.tenant_user import TenantUserOut
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
