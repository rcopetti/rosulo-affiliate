import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_public_track_click(
    client: AsyncClient, tenant: Tenant, tenant_user
):
    # Admin login
    admin_login = await client.post(
        "/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    # Configure allowed domain
    await client.put(
        "/v1/admin/integration/allowed-domains",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"allowed_domains": ["allbum.me", "*.allbum.me"]},
    )

    # Create affiliate and campaign
    invite = await client.post(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "track@example.com"},
    )
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "track@example.com",
            "password": "secret123",
            "name": "Tracker",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    aff_token = accept.json()["token"]

    campaign = await client.post(
        "/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {aff_token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Landing", "landing_url": "https://allbum.me/landing"},
    )
    assert campaign.status_code == 200
    tracking_code = campaign.json()["tracking_code"]

    # Track a click from an allowed origin
    r = await client.post(
        "/v1/tracking/track-click",
        headers={
            "Origin": "https://allbum.me",
            "User-Agent": "Mozilla/5.0",
        },
        json={
            "tracking_code": tracking_code,
            "referer": "https://example.com",
            "page_url": "https://allbum.me/landing?rc=" + tracking_code,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["campaign_id"]
    assert data["click_id"]

    # Invalid origin should be rejected
    bad = await client.post(
        "/v1/tracking/track-click",
        headers={
            "Origin": "https://evil.com",
            "User-Agent": "Mozilla/5.0",
        },
        json={
            "tracking_code": tracking_code,
            "page_url": "https://evil.com",
        },
    )
    assert bad.status_code == 403
