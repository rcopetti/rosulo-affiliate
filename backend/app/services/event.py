import uuid
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Campaign, Event, PaymentRecord, Tenant
from app.schemas.event import EventCreate


async def ingest_event(db: AsyncSession, tenant: Tenant, data: EventCreate) -> Event:
    existing_result = await db.execute(select(Event).where(Event.event_id == data.event_id))
    existing = existing_result.scalar_one_or_none()
    if existing:
        return existing

    affiliate_id = None
    campaign_id = None
    customer_id = data.customer_id

    # Resolve attribution from the strongest available source.
    if data.lead_id:
        try:
            lead = await db.get(Event, uuid.UUID(data.lead_id))
        except ValueError:
            lead = None
        if not lead or lead.type != "lead" or lead.tenant_id != tenant.id:
            raise HTTPException(status_code=400, detail="Invalid or unknown lead_id")
        campaign_id = lead.campaign_id
        affiliate_id = lead.affiliate_id
        if not customer_id:
            customer_id = lead.customer_id

    elif data.click_id:
        try:
            click = await db.get(Event, uuid.UUID(data.click_id))
        except ValueError:
            click = None
        if not click or click.type != "click" or click.tenant_id != tenant.id:
            raise HTTPException(status_code=400, detail="Invalid or unknown click_id")
        campaign_id = click.campaign_id
        affiliate_id = click.affiliate_id

    elif data.campaign_id:
        campaign_result = await db.execute(
            select(Campaign).where(
                Campaign.id == uuid.UUID(data.campaign_id),
                Campaign.tenant_id == tenant.id,
            )
        )
        campaign = campaign_result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        affiliate_id = campaign.affiliate_id
        campaign_id = campaign.id

    elif data.tracking_code:
        campaign_result = await db.execute(
            select(Campaign).where(
                Campaign.tracking_code == data.tracking_code,
                Campaign.tenant_id == tenant.id,
            )
        )
        campaign = campaign_result.scalar_one_or_none()
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        affiliate_id = campaign.affiliate_id
        campaign_id = campaign.id

    # Type-specific validation.
    if data.type == "click" and not campaign_id:
        raise HTTPException(status_code=400, detail="click requires campaign_id or tracking_code")
    if data.type == "lead" and not campaign_id:
        raise HTTPException(status_code=400, detail="lead requires click_id, campaign_id, or tracking_code")
    if data.type == "sale" and not campaign_id:
        raise HTTPException(status_code=400, detail="sale requires lead_id, click_id, campaign_id, or tracking_code")

    event = Event(
        event_id=data.event_id,
        type=data.type,
        tenant_id=tenant.id,
        campaign_id=campaign_id,
        affiliate_id=affiliate_id,
        customer_id=customer_id,
        customer_email=data.customer_email,
        amount=data.amount,
        currency=data.currency,
        payment_sequence=data.payment_sequence,
        good_date=data.good_date,
        payment_record_id=data.payment_record_id,
        referer=data.referer,
        page_url=data.page_url,
        user_agent=data.user_agent,
        ip_address=data.ip_address,
        occurred_at=data.occurred_at or datetime.utcnow(),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event
