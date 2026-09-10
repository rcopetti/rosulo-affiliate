import datetime
import time
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.db.models import Campaign, Event, Tenant
from app.schemas.tracking import TrackClick, TrackClickOut

router = APIRouter()

_rate_buckets: dict[str, list[float]] = {}


def _host_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.hostname or url


def _is_allowed(origin: str | None, allowed_domains: list[str]) -> bool:
    host = _host_from_url(origin)
    if not host:
        return False
    for domain in allowed_domains:
        if domain.startswith("*."):
            suffix = domain[2:]
            if host == suffix or host.endswith("." + suffix):
                return True
        if host == domain:
            return True
    return False


def _rate_limit(key: str, max_requests: int = 10, window: int = 60) -> bool:
    now = time.time()
    ts = _rate_buckets.get(key, [])
    ts = [t for t in ts if now - t < window]
    if len(ts) >= max_requests:
        _rate_buckets[key] = ts
        return False
    ts.append(now)
    _rate_buckets[key] = ts
    return True


@router.post("/track-click", response_model=TrackClickOut)
async def track_click(
    data: TrackClick,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Look up the campaign by public tracking code.
    result = await db.execute(
        select(Campaign).where(Campaign.tracking_code == data.tracking_code)
    )
    campaign = result.scalar_one_or_none()
    if not campaign or not campaign.active:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # Load the tenant for the CORS allowlist.
    tenant = await db.get(Tenant, campaign.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Validate the request came from an allowed domain.
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    allowed = tenant.allowed_domains or []
    if not _is_allowed(origin, allowed) and not _is_allowed(referer, allowed):
        raise HTTPException(status_code=403, detail="Invalid origin")

    # Basic bot / missing UA check.
    ua = request.headers.get("user-agent")
    if not ua:
        raise HTTPException(status_code=403, detail="Missing user agent")

    # Rate limit by IP and tracking code.
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    if not _rate_limit(f"{client_ip}:{data.tracking_code}", max_requests=10, window=60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    event = Event(
        event_id=data.event_id or f"click-{uuid.uuid4()}",
        type="click",
        tenant_id=campaign.tenant_id,
        campaign_id=campaign.id,
        affiliate_id=campaign.affiliate_id,
        customer_id=data.customer_id,
        referer=data.referer,
        page_url=data.page_url,
        user_agent=ua,
        ip_address=client_ip,
        occurred_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return {"click_id": str(event.id), "campaign_id": str(campaign.id)}
