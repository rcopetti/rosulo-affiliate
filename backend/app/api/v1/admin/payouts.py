import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_tenant, get_tenant_user
from app.db.dependencies import get_db
from app.db.models import Tenant, TenantUser
from app.schemas.payout import PayoutOut, PayoutPaymentConfirmation
from app.services import payout as payout_service

router = APIRouter()


@router.get("", response_model=list[PayoutOut])
async def list_payouts(
    tenant: Tenant = Depends(get_tenant), db: AsyncSession = Depends(get_db)
):
    return await payout_service.list_payouts(db, tenant)


@router.get("/{payout_id}", response_model=PayoutOut)
async def get_payout(
    payout_id: str,
    tenant: Tenant = Depends(get_tenant),
    db: AsyncSession = Depends(get_db),
):
    return await payout_service.get_payout(db, uuid.UUID(payout_id), tenant)


@router.post("/{payout_id}/approve", response_model=PayoutOut)
async def approve_payout(
    payout_id: str,
    tenant: Tenant = Depends(get_tenant),
    reviewer: TenantUser = Depends(get_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    payout = await payout_service.get_payout(db, uuid.UUID(payout_id), tenant)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    return await payout_service.approve_payout(db, payout, reviewer)


@router.post("/{payout_id}/reject", response_model=PayoutOut)
async def reject_payout(
    payout_id: str,
    tenant: Tenant = Depends(get_tenant),
    reviewer: TenantUser = Depends(get_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    payout = await payout_service.get_payout(db, uuid.UUID(payout_id), tenant)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    return await payout_service.reject_payout(db, payout, reviewer)


@router.post("/{payout_id}/confirm-payment", response_model=PayoutOut)
async def confirm_payout_payment(
    payout_id: str,
    data: PayoutPaymentConfirmation,
    tenant: Tenant = Depends(get_tenant),
    reviewer: TenantUser = Depends(get_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    payout = await payout_service.get_payout(db, uuid.UUID(payout_id), tenant)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    return await payout_service.confirm_payout_payment(
        db,
        payout,
        reviewer,
        data.paid_at,
        data.transfer_reference,
    )
