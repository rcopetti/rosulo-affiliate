from collections import defaultdict
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Campaign, Commission, Event, Payout


async def affiliate_dashboard(db: AsyncSession, affiliate_id: UUID, campaign_id: UUID | None = None):
    # Balance
    result = await db.execute(
        select(
            Commission.status,
            func.sum(Commission.gross_amount),
            func.sum(Commission.withholding_amount),
            func.sum(Commission.net_amount),
        ).where(Commission.affiliate_id == affiliate_id)
        .group_by(Commission.status)
    )
    balance = {
        "earned": 0.0,
        "pending": 0.0,
        "available": 0.0,
        "paid": 0.0,
        "reversed": 0.0,
        "tax_retained": 0.0,
    }
    for status, gross, withholding, net in result.all():
        if status in balance:
            balance[status] = float(gross or 0)
        balance["tax_retained"] += float(withholding or 0)

    # Leads by day
    since = datetime.utcnow() - timedelta(days=30)
    lead_query = (
        select(func.date(Event.occurred_at), func.count())
        .where(Event.affiliate_id == affiliate_id, Event.type == "lead", Event.occurred_at >= since)
        .group_by(func.date(Event.occurred_at))
    )
    if campaign_id:
        lead_query = lead_query.where(Event.campaign_id == campaign_id)
    leads = await db.execute(lead_query)
    lead_volume = {str(day): int(count) for day, count in leads.all()}

    # Sales by sequence
    sales = await db.execute(
        select(Event.payment_sequence, func.sum(Commission.gross_amount))
        .join(Commission, Commission.event_id == Event.id)
        .where(Event.affiliate_id == affiliate_id)
        .group_by(Event.payment_sequence)
    )
    sales_by_sequence = {
        seq: {"gross": float(g or 0)} for seq, g in sales.all()
    }

    payouts = await db.execute(select(Payout).where(Payout.affiliate_id == affiliate_id))
    payout_list = [
        {
            "id": str(p.id),
            "status": p.status,
            "requested_amount": p.requested_amount,
            "net_paid": p.net_paid,
        }
        for p in payouts.scalars().all()
    ]

    return {
        "balance": balance,
        "lead_volume": lead_volume,
        "sales_by_sequence": sales_by_sequence,
        "payouts": payout_list,
    }


async def tenant_dashboard(db: AsyncSession, tenant_id: UUID):
    campaigns = await db.execute(select(Campaign).where(Campaign.tenant_id == tenant_id))
    perf = []
    for c in campaigns.scalars().all():
        clicks = await db.execute(
            select(func.count()).where(Event.campaign_id == c.id, Event.type == "click")
        )
        leads = await db.execute(
            select(func.count()).where(Event.campaign_id == c.id, Event.type == "lead")
        )
        sales = await db.execute(
            select(func.count()).where(Event.campaign_id == c.id, Event.type == "sale")
        )
        perf.append(
            {
                "campaign_id": str(c.id),
                "clicks": clicks.scalar() or 0,
                "leads": leads.scalar() or 0,
                "sales": sales.scalar() or 0,
            }
        )

    liability = await db.execute(
        select(func.sum(Commission.gross_amount)).where(
            Commission.status.in_(["available", "pending"]),
            Commission.tenant_id == tenant_id if hasattr(Commission, "tenant_id") else True,
        )
    )
    return {
        "campaign_performance": perf,
        "affiliates": [],
        "commission_liability": float(liability.scalar() or 0),
        "payout_queue": [],
    }
