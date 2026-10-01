from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Commission

ZERO = Decimal("0.00")


def build_balances(rows) -> list[dict]:
    balances = defaultdict(
        lambda: {
            "earned": ZERO,
            "pending": ZERO,
            "available": ZERO,
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
        if status in {"pending", "available", "paid"}:
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
    result = await db.execute(
        select(
            Commission.currency,
            Commission.status,
            func.sum(Commission.withholding_amount),
            func.sum(Commission.net_amount),
        )
        .where(Commission.affiliate_id == affiliate_id)
        .group_by(Commission.currency, Commission.status)
    )
    return build_balances(result.all())


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
                "paid": None,
                "reversed": None,
                "tax_retained": None,
                "reversal_total": None,
                "debt": None,
            }
        )
    return response
