from collections import defaultdict
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Campaign, Commission, Event, Payout
from app.services import affiliate as affiliate_service


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
        "debt": 0.0,
        "currency": "USD",
    }
    for status, gross, withholding, net in result.all():
        if status in balance:
            balance[status] = float(gross or 0)
        balance["tax_retained"] += float(withholding or 0)
    balance["debt"] = balance["reversed"]

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
    lead_volume = [
        {"bucket": str(day), "count": int(count)} for day, count in leads.all()
    ]

    # Sales by sequence
    sales = await db.execute(
        select(Event.payment_sequence, func.count(Event.id), func.sum(Commission.gross_amount))
        .join(Commission, Commission.event_id == Event.id)
        .where(Event.affiliate_id == affiliate_id)
        .group_by(Event.payment_sequence)
    )
    sales_by_sequence = [
        {"sequence": int(seq or 1), "count": int(count), "amount": float(g or 0)}
        for seq, count, g in sales.all()
    ]

    payouts = await db.execute(select(Payout).where(Payout.affiliate_id == affiliate_id))
    payout_list = [
        {
            "id": str(p.id),
            "status": p.status,
            "requested_amount": p.requested_amount,
            "net_paid": p.net_paid,
            "currency": p.currency,
            "requested_at": p.requested_at.isoformat() if p.requested_at else None,
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
        clicks = (
            await db.execute(
                select(func.count()).where(Event.campaign_id == c.id, Event.type == "click")
            )
        ).scalar() or 0
        leads = (
            await db.execute(
                select(func.count()).where(Event.campaign_id == c.id, Event.type == "lead")
            )
        ).scalar() or 0
        sales = (
            await db.execute(
                select(func.count()).where(Event.campaign_id == c.id, Event.type == "sale")
            )
        ).scalar() or 0
        perf.append(
            {
                "campaign_id": str(c.id),
                "name": c.name,
                "clicks": clicks,
                "leads": leads,
                "sales": sales,
            }
        )

    # Commission liability grouped by month
    period_expr = func.date_trunc("month", Event.occurred_at).label("period")
    liability_result = await db.execute(
        select(
            period_expr,
            func.sum(Commission.gross_amount).label("gross"),
            func.sum(Commission.withholding_amount).label("tax"),
        )
        .join(Event, Commission.event_id == Event.id)
        .where(
            Event.tenant_id == tenant_id,
            Commission.status.in_(["available", "pending"]),
        )
        .group_by(period_expr)
    )
    commission_liability = [
        {
            "period": row.period.strftime("%Y-%m") if hasattr(row.period, "strftime") else str(row.period)[:7],
            "gross": float(row.gross or 0),
            "tax_retained": float(row.tax or 0),
        }
        for row in liability_result.all()
    ]

    # Pending payouts
    payouts_result = await db.execute(
        select(Payout).where(
            Payout.tenant_id == tenant_id,
            Payout.status == "pending_approval",
        )
    )
    payout_queue = [
        {
            "id": str(p.id),
            "requested_amount": p.requested_amount,
            "currency": p.currency,
            "status": p.status,
            "requested_at": p.requested_at.isoformat() if p.requested_at else None,
            "affiliate_id": str(p.affiliate_id),
        }
        for p in payouts_result.scalars().all()
    ]

    # Affiliate list for this tenant
    from app.db.models import Tenant as TenantModel
    tenant_obj = await db.get(TenantModel, tenant_id)
    affiliates = await affiliate_service.list_affiliates(db, tenant_obj) if tenant_obj else []

    return {
        "campaign_performance": perf,
        "affiliates": affiliates,
        "commission_liability": commission_liability,
        "payout_queue": payout_queue,
    }
