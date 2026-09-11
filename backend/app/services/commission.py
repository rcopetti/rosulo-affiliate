import uuid
from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Affiliate, AffiliateAccount, Commission, Contract, Event, PaymentRecord, Term
from app.services.contract import get_contract_for_affiliate
from app.services.tax import apply_tax


async def calculate_from_sale_event(
    db: AsyncSession, event: Event, affiliate: Affiliate
) -> Commission | None:
    contract = await get_contract_for_affiliate(db, affiliate.id)
    if not contract:
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
        return None

    if applicable.minimum_threshold is not None and event.amount < applicable.minimum_threshold:
        return None

    gross = round(event.amount * (applicable.commission_percent / 100.0), 2)

    account = await db.get(AffiliateAccount, affiliate.affiliate_account_id)
    _, withholding, net = apply_tax(account, gross)

    commission = Commission(
        event_id=event.id,
        affiliate_id=affiliate.id,
        campaign_id=event.campaign_id,
        gross_amount=gross,
        withholding_amount=withholding,
        net_amount=net,
        currency=event.currency,
        status="pending",
        available_on=event.good_date,
    )
    db.add(commission)
    await db.commit()
    await db.refresh(commission)
    return commission


async def mark_available_commissions(db: AsyncSession):
    result = await db.execute(
        select(Commission).where(
            Commission.status == "pending",
            Commission.available_on <= date.today(),
        )
    )
    for commission in result.scalars().all():
        event = await db.get(Event, commission.event_id)
        if event and event.payment_record_id:
            pr = await db.execute(
                select(PaymentRecord).where(
                    PaymentRecord.tenant_payment_id == event.payment_record_id,
                    PaymentRecord.status == "paid",
                )
            )
            if pr.scalar_one_or_none():
                commission.status = "available"
    await db.commit()


async def create_reversal(db: AsyncSession, event: Event, affiliate: Affiliate) -> Commission:
    commission = Commission(
        event_id=event.id,
        affiliate_id=affiliate.id,
        campaign_id=event.campaign_id,
        gross_amount=-event.amount,
        withholding_amount=0.0,
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
