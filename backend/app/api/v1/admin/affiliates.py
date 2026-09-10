import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_affiliate_account, get_tenant
from app.db.dependencies import get_db
from app.db.models import Affiliate, AffiliateAccount, Tenant
from app.schemas.affiliate import AffiliateCreate, AffiliateOut
from app.schemas.affiliate_account import AffiliateAccountUpdate
from app.services import affiliate as affiliate_service
from app.services import affiliate_account as acct_service

router = APIRouter()


@router.post("/register", response_model=AffiliateOut)
async def admin_create_affiliate(
    data: AffiliateCreate,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    affiliate = await acct_service.create_tenant_affiliate(db, tenant, data)
    return affiliate


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
