import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_profile_can_be_saved_without_tax_fields(client: AsyncClient, tenant: Tenant, tenant_user):
    admin_login = await client.post(
        "/api/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "profile@example.com"},
    )
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/api/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "profile@example.com",
            "password": "secret123",
            "name": "Profile Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    token = accept.json()["token"]

    # Save profile without any tax fields (no tax_status, tax_id, or tax document type).
    r = await client.patch(
        "/api/v1/affiliate/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Profile Updated",
            "country": "BR",
            "state": "SP",
            "postal_code": "01310-100",
            "paypal_email": "payouts@example.com",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["postal_code"] == "01310-100"
    assert body["paypal_email"] == "payouts@example.com"
    # Tax fields remain untouched when omitted.
    assert body["tax_status"] == "us_person"
    assert body["tax_entity_type"] == "individual"
    assert body["tax_form_type"] == "W-9"
