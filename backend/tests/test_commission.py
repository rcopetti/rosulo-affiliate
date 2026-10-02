from datetime import date

import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_sale_generates_commission(
    client: AsyncClient, tenant: Tenant, tenant_user
):
    admin_login = await client.post(
        "/api/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "commission@example.com",
            "contract_terms": [
                {
                    "commission_percent": 10.0,
                    "payment_sequence": 1,
                    "minimum_threshold": 2.05,
                }
            ],
        },
    )
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/api/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "commission@example.com",
            "password": "secret123",
            "name": "Commission Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    token = accept.json()["token"]

    camp = await client.post(
        "/api/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Commission Camp", "landing_url": "https://allbum.me/c"},
    )
    campaign_id = camp.json()["id"]

    # idempotent duplicate should not create new event
    for _ in range(2):
        r = await client.post(
            "/api/v1/events",
            headers={"X-API-Key": "test-api-key"},
            json={
                "event_id": "comm-sale-1",
                "type": "sale",
                "campaign_id": campaign_id,
                "customer_id": "cust-1",
                "amount": 2.05,
                "currency": "USD",
                "payment_sequence": 1,
                "good_date": str(date.today()),
                "payment_record_id": "comm-pay-1",
            },
        )
        assert r.status_code == 200

    eur_sale = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "commission-eur-below-threshold",
            "type": "sale",
            "campaign_id": campaign_id,
            "customer_id": "cust-eur",
            "amount": 2.04,
            "currency": "EUR",
            "payment_sequence": 1,
            "good_date": str(date.today()),
            "payment_record_id": "comm-pay-eur",
        },
    )
    assert eur_sale.status_code == 200

    # one commission from first sale
    comms = await client.get(
        "/api/v1/affiliate/commissions",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
    )
    assert comms.status_code == 200
    assert len(comms.json()) == 1
    assert comms.json()[0]["gross_amount"] == 0.21  # 10% contract term


@pytest.mark.asyncio
async def test_sale_without_matching_sequence_creates_no_commission(
    client: AsyncClient, tenant: Tenant, tenant_user
):
    admin_login = await client.post(
        "/api/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "sequence@example.com"},
    )
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/api/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "sequence@example.com",
            "password": "secret123",
            "name": "Sequence Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    token = accept.json()["token"]

    camp = await client.post(
        "/api/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Sequence Camp", "landing_url": "https://allbum.me/s"},
    )
    campaign_id = camp.json()["id"]

    # Default contract only covers payment_sequence 1.
    sale = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "seq-sale-2",
            "type": "sale",
            "campaign_id": campaign_id,
            "customer_id": "cust-2",
            "amount": 200.0,
            "payment_sequence": 2,
            "good_date": str(date.today()),
            "payment_record_id": "seq-pay-2",
        },
    )
    assert sale.status_code == 200

    comms = await client.get(
        "/api/v1/affiliate/commissions",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
    )
    assert comms.status_code == 200
    assert len(comms.json()) == 0
