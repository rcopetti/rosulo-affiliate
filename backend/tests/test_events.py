import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_event_ingestion(client: AsyncClient, tenant: Tenant, tenant_user):
    admin_login = await client.post(
        "/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "event@example.com"},
    )
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "event@example.com",
            "password": "secret123",
            "name": "Event Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    token = accept.json()["token"]

    camp = await client.post(
        "/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Event Camp", "landing_url": "https://allbum.me/e"},
    )
    campaign_id = camp.json()["id"]

    click = await client.post(
        "/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "click-1",
            "type": "click",
            "campaign_id": campaign_id,
            "customer_id": "cust-1",
            "referer": "https://google.com",
            "page_url": "https://allbum.me/landing",
        },
    )
    assert click.status_code == 200

    sale = await client.post(
        "/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "sale-1",
            "type": "sale",
            "campaign_id": campaign_id,
            "customer_id": "cust-1",
            "amount": 100.0,
            "currency": "USD",
            "payment_sequence": 1,
            "good_date": "2026-09-09",
            "payment_record_id": "pay-1",
        },
    )
    assert sale.status_code == 200
    assert sale.json()["type"] == "sale"
