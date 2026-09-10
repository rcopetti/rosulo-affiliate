from datetime import date

import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_dashboards(client: AsyncClient, tenant: Tenant):
    reg = await client.post(
        "/v1/auth/affiliate/register",
        json={
            "email": "dash@example.com",
            "password": "secret123",
            "name": "Dash Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    token = reg.json()["access_token"]

    await client.post(
        "/v1/admin/affiliates/register",
        headers={"X-API-Key": "test-api-key"},
        json={
            "email": "dash@example.com",
            "password": "secret123",
            "name": "Dash Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )

    camp = await client.post(
        "/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Dash Camp", "landing_url": "https://allbum.me/d"},
    )
    campaign_id = camp.json()["id"]

    await client.post(
        "/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "dash-click-1",
            "type": "click",
            "campaign_id": campaign_id,
            "customer_id": "cust-1",
            "referer": "https://x.com",
            "page_url": "https://allbum.me/d",
        },
    )

    a_dash = await client.get(
        "/v1/affiliate/dashboard",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
    )
    assert a_dash.status_code == 200
    assert "balance" in a_dash.json()

    t_dash = await client.get(
        "/v1/admin/dashboard",
        headers={"X-API-Key": "test-api-key"},
    )
    assert t_dash.status_code == 200
    assert "campaign_performance" in t_dash.json()
