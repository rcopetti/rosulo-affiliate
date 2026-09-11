import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_affiliate_create_campaign(
    client: AsyncClient, tenant: Tenant, tenant_user
):
    admin_login = await client.post(
        "/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "campaign@example.com"},
    )
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "campaign@example.com",
            "password": "secret123",
            "name": "Campaign Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    token = accept.json()["token"]

    r = await client.post(
        "/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Summer Push", "landing_url": "https://allbum.me/summer"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Summer Push"
    assert data["tracking_code"].startswith("ros-")
