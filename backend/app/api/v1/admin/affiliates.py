import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_tenant
from app.db.dependencies import get_db
from app.db.models import Tenant
from app.schemas.affiliate import AffiliateOut
from app.schemas.affiliate_invite import AffiliateInviteCreate, AffiliateInviteOut
from app.services import affiliate as affiliate_service
from app.services import affiliate_invite as invite_service

router = APIRouter()


@router.post("", response_model=AffiliateInviteOut)
async def admin_create_invite(
    data: AffiliateInviteCreate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    invite = await invite_service.create_invite(db, tenant, data)
    return invite


@router.get("", response_model=list[AffiliateOut])
async def admin_list_affiliates(
    tenant: Tenant = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    return await affiliate_service.list_affiliates(db, tenant)


@router.get("/{affiliate_id}", response_model=AffiliateOut)
async def admin_get_affiliate(
    affiliate_id: str,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    return await affiliate_service.get_affiliate(db, uuid.UUID(affiliate_id), tenant)


@router.post("/{affiliate_id}/approve", response_model=AffiliateOut)
async def admin_approve_affiliate(
    affiliate_id: str,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    return await affiliate_service.approve_affiliate_kyc(db, uuid.UUID(affiliate_id), tenant)


@router.post("/{affiliate_id}/reject", response_model=AffiliateOut)
async def admin_reject_affiliate(
    affiliate_id: str,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    return await affiliate_service.reject_affiliate_kyc(db, uuid.UUID(affiliate_id), tenant)
