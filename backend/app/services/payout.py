import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.money import is_supported_currency, normalize_currency_code, quantize_ledger_amount
from app.db.models import (
    Affiliate,
    Commission,
    Payout,
    PayoutCommission,
    PayoutNotification,
    PayoutPayment,
    PayoutTransition,
    Tenant,
    TenantUser,
)
from app.services.document_review import get_document_status


async def request_payout(
    db: AsyncSession,
    affiliate: Affiliate,
    currency: str,
    commission_ids: list[uuid.UUID] | None = None,
) -> Payout:
    currency = normalize_currency_code(currency)
    if not is_supported_currency(currency):
        raise HTTPException(status_code=400, detail="No available commissions")
    eligibility = (await get_document_status(db, affiliate))["payout_eligibility"]
    if not eligibility["eligible"]:
        raise HTTPException(status_code=403, detail=eligibility["reason"])

    if commission_ids is not None and not set(commission_ids):
        # The request schema rejects empty selections, but direct service
        # callers must not create a $0 payout with no links either.
        raise HTTPException(status_code=400, detail="No commissions selected")

    filters = [
        Commission.affiliate_id == affiliate.id,
        Commission.currency == currency,
        Commission.status == "available",
    ]
    distinct_ids = set(commission_ids) if commission_ids is not None else None
    if distinct_ids is not None:
        filters.append(Commission.id.in_(distinct_ids))

    result = await db.execute(
        select(Commission)
        .where(*filters)
        .order_by(Commission.id)
        .with_for_update()
    )
    commissions = result.scalars().all()

    if distinct_ids is not None:
        # Every submitted ID must resolve to an available commission owned by
        # this affiliate in this currency; anything missing means the row is
        # reserved/paid, belongs to someone else, or has another currency.
        if len(commissions) != len(distinct_ids):
            raise HTTPException(
                status_code=409,
                detail="One or more commissions are not available for payout",
            )
    elif not commissions:
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
        commission.status = "reserved"
        db.add(
            PayoutCommission(
                payout_id=payout.id,
                commission_id=commission.id,
                amount=commission.gross_amount,
                is_active=True,
            )
        )

    try:
        # The transition query autoflushes the link inserts, so an
        # active-reservation race surfaces here as well as at commit.
        await _record_transition(db, payout, None, "pending_approval", None)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if _integrity_constraint_name(exc) != "uq_payout_commissions_active_commission":
            raise
        raise HTTPException(
            status_code=409,
            detail="One or more commissions are not available for payout",
        ) from exc
    return await _load_payout_detail(db, payout.id)


def _integrity_constraint_name(exc: IntegrityError) -> str | None:
    """Return the name of the violated constraint across DBAPI drivers.

    psycopg exposes ``diag.constraint_name`` on ``exc.orig``; asyncpg puts
    ``constraint_name`` on the server error itself, which SQLAlchemy may
    surface at ``exc.orig`` or nested under its ``__cause__`` /
    ``__context__`` depending on the driver version.
    """
    queue = [exc.orig]
    seen = set()
    while queue:
        current = queue.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        diag = getattr(current, "diag", None)
        name = getattr(diag, "constraint_name", None) or getattr(
            current, "constraint_name", None
        )
        if name:
            return name
        queue.append(getattr(current, "__cause__", None))
        queue.append(getattr(current, "__context__", None))
    return None


def payout_detail_options():
    """Eagerly load everything ``PayoutOut`` serializes.

    ``affiliate.account`` and each link's ``commission``/``commission.event``
    are plain lazy relationships; resolving them during response
    serialization would raise ``MissingGreenlet`` under asyncio, so they must
    arrive with the payout row.
    """
    return (
        selectinload(Payout.affiliate).selectinload(Affiliate.account),
        selectinload(Payout.payout_commissions)
        .selectinload(PayoutCommission.commission)
        .selectinload(Commission.event),
        selectinload(Payout.payout_payment),
        selectinload(Payout.transitions),
    )


async def _load_payout_detail(db: AsyncSession, payout_id: uuid.UUID) -> Payout:
    """Re-read a payout with the full detail graph after a state change."""
    result = await db.execute(
        select(Payout)
        .where(Payout.id == payout_id)
        .options(*payout_detail_options())
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def get_payout(db: AsyncSession, payout_id: uuid.UUID, tenant: Tenant) -> Payout | None:
    result = await db.execute(
        select(Payout)
        .where(Payout.id == payout_id, Payout.tenant_id == tenant.id)
        .options(*payout_detail_options())
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
    return await _load_payout_detail(db, payout.id)


async def reject_payout(
    db: AsyncSession, payout: Payout, reviewer: TenantUser
) -> Payout:
    payout = await _lock_payout(db, payout.id)
    _verify_reviewer(payout, reviewer)
    if payout.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Payout cannot be rejected")

    commissions = await _verify_linked_commissions(db, payout)

    for link in payout.payout_commissions:
        link.is_active = False
    for commission in commissions:
        commission.status = "available"
    previous_status = payout.status
    payout.status = "rejected"
    await _record_transition(db, payout, previous_status, payout.status, reviewer)
    await db.commit()
    return await _load_payout_detail(db, payout.id)


async def confirm_payout_payment(
    db: AsyncSession,
    payout: Payout,
    reviewer: TenantUser,
    paid_at: datetime,
    transfer_reference: str,
) -> Payout:
    """Record a merchant-confirmed PayPal transfer for an approved payout.

    ``paid_at`` is the actual payment datetime the merchant entered (the
    request schema guarantees a timezone offset and no future time). The
    amount, currency, and ``paypal`` method are server-derived so a client
    cannot restate what was paid. Payment, pending notification, commission
    settlement, and the ``approved -> paid`` transition commit in a single
    transaction; Task 6's sender picks up the notification after commit.
    """
    transfer_reference = transfer_reference.strip()
    payout = await _lock_payout(db, payout.id)
    _verify_reviewer(payout, reviewer)
    if payout.status == "paid":
        # Idempotent retry: only an exact replay of the recorded payment
        # details returns the existing result; any divergence means the
        # merchant is restating a completed payment and gets a conflict.
        existing = payout.payout_payment
        if (
            existing
            and existing.paid_at == paid_at
            and existing.transfer_reference.strip() == transfer_reference
        ):
            return await _load_payout_detail(db, payout.id)
        raise HTTPException(status_code=409, detail="Payout was confirmed with different payment details")
    if payout.status != "approved":
        raise HTTPException(status_code=400, detail="Payout must be approved before payment confirmation")

    commissions = await _verify_linked_commissions(db, payout)

    db.add(
        PayoutPayment(
            payout_id=payout.id,
            amount=payout.net_paid,
            currency=payout.currency,
            payment_method="paypal",
            transfer_reference=transfer_reference,
            paid_at=paid_at,
            recorded_by_tenant_user_id=reviewer.id,
        )
    )
    db.add(PayoutNotification(payout_id=payout.id, status="pending"))

    for link in payout.payout_commissions:
        link.is_active = False
    for commission in commissions:
        commission.status = "paid"

    previous_status = payout.status
    payout.status = "paid"
    payout.paid_at = paid_at
    try:
        await _record_transition(db, payout, previous_status, payout.status, reviewer)
        await db.commit()
    except IntegrityError as exc:
        # The payout row lock serializes concurrent confirms, but migrated
        # payout_payments/payout_notifications rows can still collide with a
        # re-confirmed legacy payout.
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Payout payment already recorded"
        ) from exc
    return await _load_payout_detail(db, payout.id)


async def _verify_linked_commissions(
    db: AsyncSession, payout: Payout
) -> list[Commission]:
    """Lock and validate the commissions reserved by this payout.

    A linked commission is consistent when this payout holds its active
    ``PayoutCommission`` link and it is stored ``reserved`` — or still
    ``pending``, because migration ``e8f9a0b1c2d3`` backfilled
    ``is_active=TRUE`` on links of in-flight payouts without rewriting
    ``commission.status``. Rows linked before ``is_active`` existed are
    consistent when stored ``pending`` with no active link, because the
    parent payout's ``pending_approval``/``approved`` status alone
    expressed the reservation. Any other shape (a missing row, an active
    link held by another payout, or an unexpected status such as
    ``available`` behind an active link) means the reservation is
    inconsistent.
    """
    links = list(payout.payout_commissions)
    commission_ids = [link.commission_id for link in links]
    commissions_result = await db.execute(
        select(Commission)
        .where(Commission.id.in_(commission_ids))
        .order_by(Commission.id)
        .with_for_update()
    )
    commissions = commissions_result.scalars().all()
    if len(commissions) != len(commission_ids):
        raise HTTPException(
            status_code=409, detail="Payout commission reservation is inconsistent"
        )

    active_result = await db.execute(
        select(PayoutCommission).where(
            PayoutCommission.commission_id.in_(commission_ids),
            PayoutCommission.is_active.is_(True),
        )
    )
    active_holders = {
        link.commission_id: link.payout_id for link in active_result.scalars()
    }
    for commission in commissions:
        holder = active_holders.get(commission.id)
        if holder is None:
            if commission.status != "pending":
                raise HTTPException(
                    status_code=409,
                    detail="Payout commission reservation is inconsistent",
                )
        elif holder != payout.id:
            raise HTTPException(
                status_code=409,
                detail="Payout commission reservation is inconsistent",
            )
        elif commission.status not in ("reserved", "pending"):
            raise HTTPException(
                status_code=409,
                detail="Payout commission reservation is inconsistent",
            )
    return commissions


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
    result = await db.execute(
        select(Payout)
        .where(Payout.tenant_id == tenant.id)
        .options(*payout_detail_options())
    )
    return result.scalars().all()


def _rolling_year_start(now: datetime) -> datetime:
    """The same UTC date one year before ``now``.

    Replacing the year fails on February 29 when the prior year is not a
    leap year; the convention then is February 28.
    """
    try:
        return now.replace(year=now.year - 1)
    except ValueError:
        return now.replace(year=now.year - 1, day=28)


async def list_affiliate_payout_history(
    db: AsyncSession,
    affiliate_id: uuid.UUID,
    tenant: Tenant,
    limit: int,
    offset: int,
) -> tuple[list[Payout], int, list[dict]]:
    """Newest-first payout rows for one affiliate plus paid totals.

    ``paid_totals_by_currency`` aggregates ``PayoutPayment`` rows — the
    recorded payment fact — grouped by currency. Rows are keyed by the
    payout's affiliate and tenant so a same-tenant sibling or another
    tenant's affiliate can never contribute, and amounts never mix
    currencies.
    """
    filters = [
        Payout.affiliate_id == affiliate_id,
        Payout.tenant_id == tenant.id,
    ]
    total = (
        await db.execute(
            select(func.count()).select_from(Payout).where(*filters)
        )
    ).scalar() or 0

    result = await db.execute(
        select(Payout)
        .where(*filters)
        .options(selectinload(Payout.payout_payment))
        .order_by(Payout.requested_at.desc(), Payout.id)
        .offset(offset)
        .limit(limit)
    )
    items = list(result.scalars().all())

    now = datetime.now(timezone.utc)
    rolling_start = _rolling_year_start(now)
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    aggregates = await db.execute(
        select(
            PayoutPayment.currency,
            func.coalesce(
                func.sum(PayoutPayment.amount).filter(
                    PayoutPayment.paid_at >= rolling_start
                ),
                0,
            ).label("rolling_12_months"),
            func.coalesce(
                func.sum(PayoutPayment.amount).filter(
                    PayoutPayment.paid_at >= year_start
                ),
                0,
            ).label("year_to_date"),
        )
        .join(Payout, Payout.id == PayoutPayment.payout_id)
        .where(Payout.affiliate_id == affiliate_id, Payout.tenant_id == tenant.id)
        .group_by(PayoutPayment.currency)
        .order_by(PayoutPayment.currency)
    )
    paid_totals = [
        {
            "currency": row.currency,
            "rolling_12_months": float(row.rolling_12_months),
            "year_to_date": float(row.year_to_date),
        }
        for row in aggregates.all()
    ]
    return items, total, paid_totals
