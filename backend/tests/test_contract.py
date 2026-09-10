import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_admin_get_contract(client: AsyncClient, tenant: Tenant, tenant_user):
    admin_login = await client.post(
        "/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "contract@example.com"},
    )
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "contract@example.com",
            "password": "secret123",
            "name": "Contract Test",
            "country": "US",
            "tax_status": "us_person",
        },
    )

    affiliates = await client.get(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    account_id = accept.json()["account"]["id"]
    affiliate_id = next(a["id"] for a in affiliates.json() if a["account_id"] == account_id)

    r = await client.get(
        f"/v1/admin/affiliates/{affiliate_id}/contract",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["active"] is True
