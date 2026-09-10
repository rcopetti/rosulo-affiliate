import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_create_invite(client: AsyncClient, tenant_user):
    admin_login = await client.post(
        "/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    r = await client.post(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "new@example.com"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "new@example.com"
    assert data["status"] == "pending"
    assert "token" in data


@pytest.mark.asyncio
async def test_admin_list_affiliates_after_accept(
    client: AsyncClient, tenant_user, tenant
):
    admin_login = await client.post(
        "/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "list@example.com"},
    )
    invite_token = invite.json()["token"]

    await client.post(
        "/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "list@example.com",
            "password": "secret123",
            "name": "List Affiliate",
            "country": "US",
        },
    )

    r = await client.get(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert any(a["tenant_id"] == str(tenant.id) for a in data)
