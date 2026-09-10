from datetime import date

import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_sale_generates_commission(client: AsyncClient, tenant: Tenant):
    reg = await client.post(
        "/v1/auth/affiliate/register",
        json={
            "email": "commission@example.com",
            "password": "secret123",
            "name": "Commission Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    token = reg.json()["token"]

    admin = await client.post(
        "/v1/admin/affiliates/register",
        headers={"X-API-Key": "test-api-key"},
        json={
            "email": "commission@example.com",
            "password": "secret123",
            "name": "Commission Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    affiliate_id = admin.json()["id"]

    camp = await client.post(
        "/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Commission Camp", "landing_url": "https://allbum.me/c"},
    )
    campaign_id = camp.json()["id"]

    # idempotent duplicate should not create new event
    for _ in range(2):
        r = await client.post(
            "/v1/events",
            headers={"X-API-Key": "test-api-key"},
            json={
                "event_id": "comm-sale-1",
                "type": "sale",
                "campaign_id": campaign_id,
                "customer_id": "cust-1",
                "amount": 100.0,
                "payment_sequence": 1,
                "good_date": str(date.today()),
                "payment_record_id": "comm-pay-1",
            },
        )
        assert r.status_code == 200

    # one commission from first sale
    comms = await client.get(
        "/v1/affiliate/commissions",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
    )
    assert comms.status_code == 200
    assert len(comms.json()) == 1
    assert comms.json()[0]["gross_amount"] == 10.0  # 10% default term
