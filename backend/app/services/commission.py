from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, or_, select
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


def utc_midnight(d: date) -> datetime:
    """Return the UTC-midnight instant a merchant due date becomes available."""
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


async def calculate_from_sale_event(
    db: AsyncSession, event: Event, affiliate: Affiliate
) -> Commission | None:
    if event.good_date is None:
        # Sale events ingested by older app versions may lack the merchant
        # due date; there is no date to derive availability from, so record
        # why no commission was created instead of inventing one.
        event.commission_status = "missing_good_date"
        await db.commit()
        return None

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
        available_on=event.good_date,
        available_at=utc_midnight(event.good_date),
    )
    db.add(commission)
    await db.commit()
    await db.refresh(commission)
    return commission


async def mature_due_commissions(db: AsyncSession, now_utc: datetime | None = None) -> int:
    """Promote pending commissions whose merchant due date has arrived.

    Rows are selected in deterministic order and locked with
    ``FOR UPDATE ... SKIP LOCKED`` so overlapping scheduled runs never
    promote the same row twice; promotion is conditional on the row still
    being ``pending``. Commissions holding a reservation — an active
    ``PayoutCommission`` link or a legacy link whose parent payout is still
    ``pending_approval``/``approved`` — are skipped.

    Rows written by an older app version after the expand migration may have
    a null ``available_at``; the due instant is then derived as UTC midnight
    of ``Event.good_date`` and both ``available_at`` and the legacy
    ``available_on`` are backfilled from it.
    """
    if now_utc is None:
        now_utc = datetime.now(timezone.utc)

    active_reservation = (
        select(PayoutCommission.id)
        .join(Payout, Payout.id == PayoutCommission.payout_id)
        .where(
            PayoutCommission.commission_id == Commission.id,
            or_(
                PayoutCommission.is_active.is_(True),
                Payout.status.in_(("pending_approval", "approved")),
            ),
        )
        .exists()
    )
    result = await db.execute(
        select(Commission, Event)
        .join(Event, Event.id == Commission.event_id)
        .where(
            Commission.status == "pending",
            or_(
                Commission.available_at <= now_utc,
                Commission.available_at.is_(None),
            ),
            ~active_reservation,
        )
        .order_by(Commission.id)
        .with_for_update(of=Commission, skip_locked=True)
    )
    promoted = 0
    for commission, event in result.all():
        due_at = commission.available_at
        if due_at is None:
            if event.good_date is None:
                continue
            due_at = utc_midnight(event.good_date)
            commission.available_at = due_at
            commission.available_on = event.good_date
        if due_at <= now_utc:
            commission.status = "available"
            promoted += 1
    await db.commit()
    return promoted


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
