from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_payout_flow(client: AsyncClient, tenant: Tenant):
    reg = await client.post(
        "/v1/auth/affiliate/register",
        json={
            "email": "payout@example.com",
            "password": "secret123",
            "name": "Payout Tester",
            "country": "US",
            "tax_status": "us_person",
            "paypal_email": "payout@example.com",
        },
    )
    token = reg.json()["access_token"]

    admin = await client.post(
        "/v1/admin/affiliates/register",
        headers={"X-API-Key": "test-api-key"},
        json={
            "email": "payout@example.com",
            "password": "secret123",
            "name": "Payout Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    affiliate_id = admin.json()["id"]

    # create campaign
    camp = await client.post(
        "/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Payout Camp", "landing_url": "https://allbum.me/p"},
    )
    campaign_id = camp.json()["id"]

    # approve KYC
    await client.post(
        f"/v1/admin/affiliates/{affiliate_id}/approve",
        headers={"X-API-Key": "test-api-key"},
    )

    # sale event with payment record
    await client.post(
        "/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "payout-sale-1",
            "type": "sale",
            "campaign_id": campaign_id,
            "customer_id": "cust-1",
            "amount": 100.0,
            "currency": "USD",
            "payment_sequence": 1,
            "good_date": str(date.today()),
            "payment_record_id": "payout-pay-1",
        },
    )

    # payment record webhook
    await client.post(
        "/v1/webhooks/tenant",
        headers={"X-API-Key": "test-api-key"},
        json={
            "payment_record_id": "payout-pay-1",
            "customer_id": "cust-1",
            "amount": 100.0,
            "currency": "USD",
            "sequence_number": 1,
            "status": "paid",
        },
    )

    # request payout
    req = await client.post(
        "/v1/affiliate/payout-requests",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
    )
    assert req.status_code == 200
    assert req.json()["status"] == "pending_approval"
    payout_id = req.json()["id"]

    # approve payout
    aprv = await client.post(
        f"/v1/admin/payouts/{payout_id}/approve",
        headers={"X-API-Key": "test-api-key"},
    )
    assert aprv.status_code == 200
    assert aprv.json()["status"] == "approved"
