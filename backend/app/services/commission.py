from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.money import is_supported_currency, quantize_ledger_amount
from app.db.models import (
    Affiliate,
    AffiliateAccount,
    Commission,
    Event,
    Payout,
    PayoutCommission,
    Term,
)
from app.services.contract import get_contract_for_affiliate
from app.services.tax import apply_tax


async def calculate_from_sale_event(
    db: AsyncSession, event: Event, affiliate: Affiliate
) -> Commission | None:
    if not is_supported_currency(event.currency):
        event.commission_status = "currency_unsupported"
        await db.commit()
        return None

    was_held_for_currency = event.commission_status == "currency_unsupported"
    contract = await get_contract_for_affiliate(db, affiliate.id)
    if not contract:
        if was_held_for_currency:
            event.commission_status = None
            await db.commit()
        return None

    today = date.today()
    result = await db.execute(
        select(Term).where(
            Term.contract_id == contract.id,
            or_(
                Term.payment_sequence == event.payment_sequence,
                and_(Term.payment_sequence.is_(None), Term.sequence_pattern == "*"),
            ),
            and_(
                or_(Term.effective_from.is_(None), Term.effective_from <= today),
                or_(Term.effective_to.is_(None), Term.effective_to >= today),
            ),
        )
    )
    terms = result.scalars().all()

    applicable = None
    for term in terms:
        if term.payment_sequence == event.payment_sequence:
            applicable = term
            break
        if term.payment_sequence is None and term.sequence_pattern == "*":
            applicable = term

    # No term covers this payment sequence: the sale stays a merchant record only.
    if not applicable:
        if was_held_for_currency:
            event.commission_status = None
            await db.commit()
        return None

    if applicable.minimum_threshold is not None and event.amount < applicable.minimum_threshold:
        if was_held_for_currency:
            event.commission_status = None
            await db.commit()
        return None

    gross = quantize_ledger_amount(
        event.amount * Decimal(str(applicable.commission_percent)) / Decimal(100),
        event.currency,
    )

    account = await db.get(AffiliateAccount, affiliate.affiliate_account_id)
    _, withholding, net = apply_tax(account, gross)
    if was_held_for_currency:
        event.commission_status = None

    commission = Commission(
        event_id=event.id,
        affiliate_id=affiliate.id,
        campaign_id=event.campaign_id,
        gross_amount=gross,
        withholding_amount=withholding,
        net_amount=net,
        currency=event.currency,
        status="pending",
        available_on=(event.good_date or today) + timedelta(days=14),
    )
    db.add(commission)
    await db.commit()
    await db.refresh(commission)
    return commission


async def mark_available_commissions(db: AsyncSession, affiliate_id: UUID):
    active_reservation = (
        select(PayoutCommission.id)
        .join(Payout, Payout.id == PayoutCommission.payout_id)
        .where(
            PayoutCommission.commission_id == Commission.id,
            Payout.status.in_(("pending_approval", "approved")),
        )
        .exists()
    )
    await db.execute(
        update(Commission)
        .where(
            Commission.affiliate_id == affiliate_id,
            Commission.status == "pending",
            Commission.available_on <= date.today(),
            ~active_reservation,
        )
        .values(status="available")
    )
    await db.commit()


async def create_reversal(db: AsyncSession, event: Event, affiliate: Affiliate) -> Commission:
    commission = Commission(
        event_id=event.id,
        affiliate_id=affiliate.id,
        campaign_id=event.campaign_id,
        gross_amount=-event.amount,
        withholding_amount=Decimal("0.00"),
        net_amount=-event.amount,
        currency=event.currency,
        status="reversed",
    )
    db.add(commission)
    await db.commit()
    await db.refresh(commission)
    return commission


async def list_commissions(db: AsyncSession, affiliate: Affiliate, status: str | None = None):
    query = select(Commission).where(Commission.affiliate_id == affiliate.id)
    if status:
        query = query.where(Commission.status == status)
    result = await db.execute(query)
    return result.scalars().all()
