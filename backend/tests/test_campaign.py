import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_affiliate_create_campaign(client: AsyncClient, tenant: Tenant):
    # register as affiliate
    reg = await client.post(
        "/v1/auth/affiliate/register",
        json={
            "email": "campaign@example.com",
            "password": "secret123",
            "name": "Campaign Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    token = reg.json()["token"]

    # create per-tenant affiliate
    admin = await client.post(
        "/v1/admin/affiliates/register",
        headers={"X-API-Key": "test-api-key"},
        json={
            "email": "campaign@example.com",
            "password": "secret123",
            "name": "Campaign Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )

    r = await client.post(
        "/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Summer Push", "landing_url": "https://allbum.me/summer"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Summer Push"
    assert data["tracking_code"].startswith("ros-")
