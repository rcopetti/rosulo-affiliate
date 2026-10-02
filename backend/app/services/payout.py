import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import is_supported_currency, normalize_currency_code, quantize_ledger_amount
from app.db.models import (
    Affiliate,
    Commission,
    PaymentRecord,
    Payout,
    PayoutCommission,
    PayoutTransition,
    Tenant,
    TenantUser,
)
from app.services.commission import mark_available_commissions
from app.services.document_review import get_document_status


async def request_payout(
    db: AsyncSession, affiliate: Affiliate, currency: str
) -> Payout:
    currency = normalize_currency_code(currency)
    if not is_supported_currency(currency):
        raise HTTPException(status_code=400, detail="No available commissions")
    eligibility = (await get_document_status(db, affiliate))["payout_eligibility"]
    if not eligibility["eligible"]:
        raise HTTPException(status_code=403, detail=eligibility["reason"])

    await mark_available_commissions(db, affiliate.id)
    result = await db.execute(
        select(Commission)
        .where(
            Commission.affiliate_id == affiliate.id,
            Commission.status == "available",
            Commission.currency == currency,
        )
        .order_by(Commission.id)
        .with_for_update()
    )
    commissions = result.scalars().all()
    if not commissions:
        raise HTTPException(status_code=400, detail="No available commissions")

    gross = quantize_ledger_amount(
        sum((c.gross_amount for c in commissions), Decimal("0.00")), currency
    )
    withholding = quantize_ledger_amount(
        sum((c.withholding_amount for c in commissions), Decimal("0.00")), currency
    )
    net = quantize_ledger_amount(
        sum((c.net_amount for c in commissions), Decimal("0.00")), currency
    )

    payout = Payout(
        affiliate_id=affiliate.id,
        tenant_id=affiliate.tenant_id,
        requested_amount=gross,
        approved_amount=gross,
        withholding_total=withholding,
        net_paid=net,
        currency=currency,
        status="pending_approval",
    )
    db.add(payout)
    await db.flush()

    for commission in commissions:
        commission.status = "pending"
        db.add(
            PayoutCommission(
                payout_id=payout.id,
                commission_id=commission.id,
                amount=commission.gross_amount,
            )
        )
    await _record_transition(db, payout, None, "pending_approval", None)

    await db.commit()
    await db.refresh(payout)
    return payout


async def get_payout(db: AsyncSession, payout_id: uuid.UUID, tenant: Tenant) -> Payout | None:
    result = await db.execute(
        select(Payout).where(Payout.id == payout_id, Payout.tenant_id == tenant.id)
    )
    return result.scalar_one_or_none()


async def approve_payout(
    db: AsyncSession, payout: Payout, reviewer: TenantUser
) -> Payout:
    payout = await _lock_payout(db, payout.id)
    _verify_reviewer(payout, reviewer)
    if payout.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Payout not in pending_approval")
    previous_status = payout.status
    payout.status = "approved"
    payout.approved_at = datetime.now(timezone.utc)
    await _record_transition(db, payout, previous_status, payout.status, reviewer)
    await db.commit()
    await db.refresh(payout)
    return payout


async def reject_payout(
    db: AsyncSession, payout: Payout, reviewer: TenantUser
) -> Payout:
    payout = await _lock_payout(db, payout.id)
    _verify_reviewer(payout, reviewer)
    if payout.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Payout cannot be rejected")

    commission_ids = [item.commission_id for item in payout.payout_commissions]
    commissions_result = await db.execute(
        select(Commission).where(Commission.id.in_(commission_ids)).with_for_update()
    )
    commissions = commissions_result.scalars().all()
    if len(commissions) != len(commission_ids) or any(
        commission.status != "pending" for commission in commissions
    ):
        raise HTTPException(status_code=409, detail="Payout commission reservation is inconsistent")

    for commission in commissions:
        commission.status = "available"
    previous_status = payout.status
    payout.status = "rejected"
    await _record_transition(db, payout, previous_status, payout.status, reviewer)
    await db.commit()
    await db.refresh(payout)
    return payout


async def confirm_payout_payment(
    db: AsyncSession,
    payout: Payout,
    reviewer: TenantUser,
    payment_method: str,
    transfer_reference: str,
) -> Payout:
    payout = await _lock_payout(db, payout.id)
    _verify_reviewer(payout, reviewer)
    if payout.status == "paid":
        existing = payout.payment_record
        if (
            existing
            and existing.payment_method == payment_method
            and existing.transfer_reference == transfer_reference
        ):
            return payout
        raise HTTPException(status_code=409, detail="Payout was confirmed with different payment details")
    if payout.status != "approved":
        raise HTTPException(status_code=400, detail="Payout must be approved before payment confirmation")

    commission_ids = [item.commission_id for item in payout.payout_commissions]
    commissions_result = await db.execute(
        select(Commission).where(Commission.id.in_(commission_ids)).with_for_update()
    )
    commissions = commissions_result.scalars().all()
    if len(commissions) != len(commission_ids) or any(
        commission.status != "pending" for commission in commissions
    ):
        raise HTTPException(status_code=409, detail="Payout commission reservation is inconsistent")

    paid_at = datetime.now(timezone.utc)
    payment_record = PaymentRecord(
        tenant_id=payout.tenant_id,
        amount=payout.net_paid,
        currency=payout.currency,
        paid_at=paid_at,
        status="paid",
        record_type="affiliate_payout",
        payout_id=payout.id,
        payment_method=payment_method,
        transfer_reference=transfer_reference,
        recorded_by_tenant_user_id=reviewer.id,
    )
    db.add(payment_record)
    for commission in commissions:
        commission.status = "paid"

    previous_status = payout.status
    payout.status = "paid"
    payout.paid_at = paid_at
    await _record_transition(db, payout, previous_status, payout.status, reviewer)
    await db.commit()
    await db.refresh(payout)
    return payout


async def _lock_payout(db: AsyncSession, payout_id: uuid.UUID) -> Payout:
    result = await db.execute(
        select(Payout)
        .where(Payout.id == payout_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


def _verify_reviewer(payout: Payout, reviewer: TenantUser) -> None:
    if reviewer.tenant_id != payout.tenant_id:
        raise HTTPException(status_code=403, detail="Payout belongs to another tenant")


async def _record_transition(
    db: AsyncSession,
    payout: Payout,
    from_status: str | None,
    to_status: str,
    reviewer: TenantUser | None,
) -> None:
    result = await db.execute(
        select(func.coalesce(func.max(PayoutTransition.sequence), 0)).where(
            PayoutTransition.payout_id == payout.id
        )
    )
    db.add(
        PayoutTransition(
            payout_id=payout.id,
            sequence=result.scalar_one() + 1,
            from_status=from_status,
            to_status=to_status,
            actor_tenant_user_id=reviewer.id if reviewer else None,
        )
    )


async def list_payouts(db: AsyncSession, tenant: Tenant):
    result = await db.execute(select(Payout).where(Payout.tenant_id == tenant.id))
    return result.scalars().all()
