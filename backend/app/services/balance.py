from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Commission, Payout, PayoutCommission

ZERO = Decimal("0.00")


def _logical_status():
    """Stored commission status with legacy reservations folded into ``reserved``.

    A commission still stored as ``pending`` counts as reserved when an
    active ``PayoutCommission`` link — or, for rows written before
    ``is_active`` existed, a link whose parent payout is
    ``pending_approval``/``approved`` — holds it. This mirrors the
    reservation predicate used by ``mature_due_commissions``.
    """
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
    return case(
        (and_(Commission.status == "pending", active_reservation), "reserved"),
        else_=Commission.status,
    )


def build_balances(rows) -> list[dict]:
    balances = defaultdict(
        lambda: {
            "earned": ZERO,
            "pending": ZERO,
            "available": ZERO,
            "reserved": ZERO,
            "paid": ZERO,
            "reversed": ZERO,
            "tax_retained": ZERO,
            "reversal_total": ZERO,
        }
    )
    for currency, status, withholding, net in rows:
        balance = balances[currency]
        net_amount = net or ZERO
        balance["earned"] += net_amount
        balance["tax_retained"] += withholding or ZERO
        if status in {"pending", "available", "reserved", "paid"}:
            balance[status] += net_amount
        if status == "reversed":
            balance["reversed"] += net_amount
            if net_amount < 0:
                balance["reversal_total"] += abs(net_amount)

    return [
        {
            "currency": currency,
            **amounts,
        }
        for currency, amounts in sorted(balances.items())
    ]


async def get_balances(db: AsyncSession, affiliate_id: UUID) -> list[dict]:
    logical_status = _logical_status()
    result = await db.execute(
        select(
            Commission.currency,
            logical_status,
            func.sum(Commission.withholding_amount),
            func.sum(Commission.net_amount),
        )
        .where(Commission.affiliate_id == affiliate_id)
        .group_by(Commission.currency, logical_status)
    )
    return build_balances(result.all())


async def list_commissions_with_logical_status(
    db: AsyncSession, affiliate_id: UUID
) -> list[tuple[Commission, str]]:
    """Each affiliate commission paired with its logical (exposed) status."""
    result = await db.execute(
        select(Commission, _logical_status().label("logical_status"))
        .where(Commission.affiliate_id == affiliate_id)
        .order_by(Commission.created_at, Commission.id)
    )
    return result.all()


def add_legacy_balance_fields(balances: list[dict]) -> dict:
    response = {"balances_by_currency": balances}
    if len(balances) == 1:
        response.update(balances[0])
        response["debt"] = balances[0]["reversal_total"]
    elif not balances:
        response.update(
            {
                "currency": "USD",
                "earned": ZERO,
                "pending": ZERO,
                "available": ZERO,
                "reserved": ZERO,
                "paid": ZERO,
                "reversed": ZERO,
                "tax_retained": ZERO,
                "reversal_total": ZERO,
                "debt": ZERO,
            }
        )
    else:
        response.update(
            {
                "currency": None,
                "earned": None,
                "pending": None,
                "available": None,
                "reserved": None,
                "paid": None,
                "reversed": None,
                "tax_retained": None,
                "reversal_total": None,
                "debt": None,
            }
        )
    return response
