import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_tenant_user_login(client: AsyncClient, tenant_user):
    login = await client.post(
        "/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    assert login.status_code == 200
    body = login.json()
    assert "token" in body
    assert body["tenant"]["name"] == "allbum"


@pytest.mark.asyncio
async def test_affiliate_invite_accept_and_login(
    client: AsyncClient, tenant, tenant_user
):
    # Admin creates an invite
    admin_login = await client.post(
        "/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite_resp = await client.post(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "aff@example.com",
            "contract_terms": [
                {"commission_percent": 10.0, "payment_sequence": 1}
            ],
        },
    )
    assert invite_resp.status_code == 200
    invite = invite_resp.json()
    assert invite["status"] == "pending"
    assert "token" in invite

    # Affiliate accepts the invite
    accept = await client.post(
        "/v1/auth/affiliate/accept-invite",
        json={
            "token": invite["token"],
            "email": "aff@example.com",
            "password": "secret123",
            "name": "Test Affiliate",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    assert accept.status_code == 200
    body = accept.json()
    assert "token" in body
    assert body["account"]["email"] == "aff@example.com"
    assert len(body["tenants"]) == 1

    # Affiliate logs in
    login = await client.post(
        "/v1/auth/affiliate/login",
        json={"email": "aff@example.com", "password": "secret123"},
    )
    assert login.status_code == 200
    assert "token" in login.json()
