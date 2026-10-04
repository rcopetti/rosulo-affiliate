import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_tenant, get_tenant_user
from app.db.dependencies import get_db
from app.db.models import Tenant, TenantUser
from app.schemas.payout import PayoutOut, PayoutPaymentConfirmation
from app.services import payout as payout_service
from app.services import payout_notification as notification_service

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
    payout = await payout_service.get_payout(db, uuid.UUID(payout_id), tenant)
    if not payout:
        # Same 404 for unknown and cross-tenant IDs: never reveal existence.
        raise HTTPException(status_code=404, detail="Payout not found")
    return payout


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
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(get_tenant),
    reviewer: TenantUser = Depends(get_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    payout = await payout_service.get_payout(db, uuid.UUID(payout_id), tenant)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    confirmed = await payout_service.confirm_payout_payment(
        db,
        payout,
        reviewer,
        data.paid_at,
        data.transfer_reference,
    )
    # Send only after the payment transaction committed. The task re-opens
    # its own session and atomically claims the notification, so an
    # idempotent confirm replay that enqueues a second task is a no-op for
    # the loser — and a send failure never reverts the recorded payment.
    background_tasks.add_task(
        notification_service.send_payout_notification, confirmed.id
    )
    return confirmed


@router.post("/{payout_id}/retry-notification", response_model=PayoutOut)
async def retry_payout_notification(
    payout_id: str,
    background_tasks: BackgroundTasks,
    tenant: Tenant = Depends(get_tenant),
    reviewer: TenantUser = Depends(get_tenant_user),
    db: AsyncSession = Depends(get_db),
):
    payout = await payout_service.get_payout(db, uuid.UUID(payout_id), tenant)
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    updated = await payout_service.retry_payout_notification(db, payout)
    background_tasks.add_task(
        notification_service.send_payout_notification, updated.id
    )
    return updated
