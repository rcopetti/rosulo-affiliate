import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_click_tracking_flow(client: AsyncClient, tenant: Tenant, tenant_user):
    admin_login = await client.post(
        "/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

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

    # Click event via API key using the tracking_code
    click = await client.post(
        "/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "click-001",
            "type": "click",
            "tracking_code": tracking_code,
            "referer": "https://example.com",
            "page_url": "https://allbum.me/landing",
        },
    )
    assert click.status_code == 200
    click_id = click.json()["id"]

    # Lead event using click_id
    lead = await client.post(
        "/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "lead-001",
            "type": "lead",
            "click_id": click_id,
            "customer_id": "user-123",
            "customer_email": "jo***e@example.com",
        },
    )
    assert lead.status_code == 200
    lead_id = lead.json()["id"]

    # Sale event using lead_id
    sale = await client.post(
        "/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "sale-001",
            "type": "sale",
            "lead_id": lead_id,
            "amount": 100.0,
            "currency": "USD",
            "payment_sequence": 1,
        },
    )
    assert sale.status_code == 200
    assert sale.json()["type"] == "sale"
