from datetime import date

import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_payout_flow(client: AsyncClient, tenant: Tenant, tenant_user, monkeypatch):
    admin_login = await client.post(
        "/api/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "payout@example.com"},
    )
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/api/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "payout@example.com",
            "password": "secret123",
            "name": "Payout Tester",
            "country": "US",
            "tax_status": "us_person",
            "paypal_email": "payout@example.com",
        },
    )
    token = accept.json()["token"]

    affiliates = await client.get(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    account_id = accept.json()["account"]["id"]
    affiliate_id = next(a["id"] for a in affiliates.json() if a["account_id"] == account_id)

    # create campaign
    camp = await client.post(
        "/api/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Payout Camp", "landing_url": "https://allbum.me/p"},
    )
    campaign_id = camp.json()["id"]

    monkeypatch.setattr(
        "app.services.affiliate_account.put_document",
        lambda document_id, content: f"private/{document_id}",
    )
    affiliate_headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": str(tenant.id),
    }
    uploaded = await client.post(
        "/api/v1/affiliate/documents",
        headers=affiliate_headers,
        data={"type": "W-9"},
        files={"file": ("w9.pdf", b"tax document", "application/pdf")},
    )
    document_id = uploaded.json()["id"]
    reviewed = await client.post(
        f"/api/v1/admin/affiliates/{affiliate_id}/documents/{document_id}/review",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "approved"},
    )
    assert reviewed.status_code == 200

    # sale event with payment record
    await client.post(
        "/api/v1/events",
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
        "/api/v1/webhooks/tenant",
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

    eur_sale = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "payout-sale-eur",
            "type": "sale",
            "campaign_id": campaign_id,
            "customer_id": "cust-eur",
            "amount": 100.0,
            "currency": "EUR",
            "payment_sequence": 1,
            "good_date": str(date.today()),
            "payment_record_id": "payout-pay-eur",
        },
    )
    assert eur_sale.status_code == 200
    await client.post(
        "/api/v1/webhooks/tenant",
        headers={"X-API-Key": "test-api-key"},
        json={
            "payment_record_id": "payout-pay-eur",
            "customer_id": "cust-eur",
            "amount": 100.0,
            "currency": "EUR",
            "sequence_number": 1,
            "status": "paid",
        },
    )

    # request payout
    req = await client.post(
        "/api/v1/affiliate/payout-requests",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"currency": "USD"},
    )
    assert req.status_code == 200
    assert req.json()["status"] == "pending_approval"
    assert req.json()["currency"] == "USD"
    assert req.json()["requested_amount"] == 10.0
    payout_id = req.json()["id"]

    commissions = await client.get(
        "/api/v1/affiliate/commissions",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
    )
    by_currency = {commission["currency"]: commission for commission in commissions.json()}
    assert by_currency["USD"]["status"] == "pending"
    assert by_currency["EUR"]["status"] == "available"

    # approve payout
    aprv = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert aprv.status_code == 200
    assert aprv.json()["status"] == "approved"
