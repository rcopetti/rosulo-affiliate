import uuid
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Affiliate, Commission, Payout, PayoutCommission, Tenant


async def request_payout(db: AsyncSession, affiliate: Affiliate) -> Payout:
    if not affiliate.kyc_approved_for_payout:
        raise HTTPException(status_code=403, detail="KYC not approved")

    result = await db.execute(
        select(Commission).where(
            Commission.affiliate_id == affiliate.id,
            Commission.status == "available",
        )
    )
    commissions = result.scalars().all()
    if not commissions:
        raise HTTPException(status_code=400, detail="No available commissions")

    gross = sum(c.gross_amount for c in commissions)
    withholding = sum(c.withholding_amount for c in commissions)
    net = sum(c.net_amount for c in commissions)

    payout = Payout(
        affiliate_id=affiliate.id,
        tenant_id=affiliate.tenant_id,
        requested_amount=gross,
        approved_amount=gross,
        withholding_total=withholding,
        net_paid=net,
        currency="USD",
        status="pending_approval",
    )
    db.add(payout)
    await db.flush()

    for c in commissions:
        c.status = "pending"
        db.add(PayoutCommission(payout_id=payout.id, commission_id=c.id, amount=c.gross_amount))

    await db.commit()
    await db.refresh(payout)
    return payout


async def get_payout(db: AsyncSession, payout_id: uuid.UUID, tenant: Tenant) -> Payout | None:
    result = await db.execute(
        select(Payout).where(Payout.id == payout_id, Payout.tenant_id == tenant.id)
    )
    return result.scalar_one_or_none()


async def approve_payout(db: AsyncSession, payout: Payout) -> Payout:
    if payout.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Payout not in pending_approval")
    payout.status = "approved"
    payout.approved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(payout)
    return payout


async def reject_payout(db: AsyncSession, payout: Payout) -> Payout:
    if payout.status not in ("requested", "pending_approval"):
        raise HTTPException(status_code=400, detail="Payout cannot be rejected")
    payout.status = "rejected"
    result = await db.execute(
        select(Commission).where(Commission.id.in_([pc.commission_id for pc in payout.payout_commissions]))
    )
    for commission in result.scalars().all():
        commission.status = "available"
    await db.commit()
    await db.refresh(payout)
    return payout


async def list_payouts(db: AsyncSession, tenant: Tenant):
    result = await db.execute(select(Payout).where(Payout.tenant_id == tenant.id))
    return result.scalars().all()
