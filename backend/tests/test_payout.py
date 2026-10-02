import asyncio
from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.db.models import Tenant
from app.db.session import async_session
from app.queue.handlers import handle_payout
from app.services.commission import mark_available_commissions


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
    sale_date = date.today() - timedelta(days=15)
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
            "good_date": str(sale_date),
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

    mature_eur_sale = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "payout-sale-eur-matured",
            "type": "sale",
            "campaign_id": campaign_id,
            "customer_id": "cust-eur-matured",
            "amount": 100.0,
            "currency": "EUR",
            "payment_sequence": 1,
            "good_date": str(sale_date),
            "payment_record_id": "payout-pay-eur-matured",
        },
    )
    assert mature_eur_sale.status_code == 200

    # request payout
    maturity_count = 0
    both_matured = asyncio.Event()

    async def synchronize_maturity(db, target_affiliate_id):
        nonlocal maturity_count
        await mark_available_commissions(db, target_affiliate_id)
        maturity_count += 1
        if maturity_count == 2:
            both_matured.set()
        await both_matured.wait()

    monkeypatch.setattr("app.services.payout.mark_available_commissions", synchronize_maturity)
    concurrent_requests = await asyncio.gather(
        *(
            client.post(
                "/api/v1/affiliate/payout-requests",
                headers=affiliate_headers,
                json={"currency": "USD"},
            )
            for _ in range(2)
        )
    )
    assert sorted(response.status_code for response in concurrent_requests) == [200, 400]
    req = next(response for response in concurrent_requests if response.status_code == 200)
    assert req.json()["status"] == "pending_approval"
    assert req.json()["currency"] == "USD"
    assert req.json()["requested_amount"] == 10.0
    payout_id = req.json()["id"]

    commissions = await client.get(
        "/api/v1/affiliate/commissions",
        headers=affiliate_headers,
    )
    by_currency = {}
    for commission in commissions.json():
        by_currency.setdefault(commission["currency"], []).append(commission)
    assert by_currency["USD"][0]["status"] == "pending"
    assert by_currency["USD"][0]["available_on"] == str(sale_date + timedelta(days=14))
    assert sorted(item["status"] for item in by_currency["EUR"]) == ["available", "pending"]
    assert sorted(item["available_on"] for item in by_currency["EUR"]) == [
        str(sale_date + timedelta(days=14)),
        str(date.today() + timedelta(days=14)),
    ]

    premature_payment = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"payment_method": "bank_transfer", "transfer_reference": "bank-tx-123"},
    )
    assert premature_payment.status_code == 400

    # approve payout
    aprv = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert aprv.status_code == 200
    assert aprv.json()["status"] == "approved"

    paypal_webhook = await client.post("/api/v1/webhooks/paypal", json={})
    assert paypal_webhook.status_code == 410

    async def unexpected_provider_transfer(*args, **kwargs):
        raise AssertionError("Manual payouts must not dispatch to PayPal")

    monkeypatch.setattr("app.integrations.paypal.send_payout", unexpected_provider_transfer)
    async with async_session() as db:
        await handle_payout(db, payout_id)
    approved_payout = await client.get(
        f"/api/v1/admin/payouts/{payout_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approved_payout.json()["status"] == "approved"

    duplicate_approval = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert duplicate_approval.status_code == 400

    commissions = await client.get(
        "/api/v1/affiliate/commissions",
        headers=affiliate_headers,
    )
    by_currency = {commission["currency"]: commission for commission in commissions.json()}
    assert by_currency["USD"]["status"] == "pending"

    payment_details = {
        "payment_method": "bank_transfer",
        "transfer_reference": "bank-tx-123",
    }
    confirmed = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payment_details,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "paid"
    assert confirmed.json()["payment_record"]["payment_method"] == "bank_transfer"
    assert confirmed.json()["payment_record"]["transfer_reference"] == "bank-tx-123"
    assert confirmed.json()["payment_record"]["amount"] == confirmed.json()["net_paid"]
    assert confirmed.json()["payment_record"]["currency"] == confirmed.json()["currency"]
    assert [item["to_status"] for item in confirmed.json()["transitions"]] == [
        "pending_approval",
        "approved",
        "paid",
    ]
    assert confirmed.json()["transitions"][-1]["actor_tenant_user_id"] is not None

    duplicate_confirmation = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payment_details,
    )
    assert duplicate_confirmation.status_code == 200
    assert duplicate_confirmation.json()["payment_record"]["id"] == confirmed.json()["payment_record"]["id"]

    conflicting_confirmation = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"payment_method": "bank_transfer", "transfer_reference": "different-ref"},
    )
    assert conflicting_confirmation.status_code == 409

    commissions = await client.get(
        "/api/v1/affiliate/commissions",
        headers=affiliate_headers,
    )
    by_currency = {}
    for commission in commissions.json():
        by_currency.setdefault(commission["currency"], []).append(commission)
    assert by_currency["USD"][0]["status"] == "paid"
    assert sorted(item["status"] for item in by_currency["EUR"]) == ["available", "pending"]

    balance = await client.get("/api/v1/affiliate/balance", headers=affiliate_headers)
    eur_balance = next(item for item in balance.json()["balances_by_currency"] if item["currency"] == "EUR")
    assert eur_balance["available"] == 10.0
    assert eur_balance["pending"] == 10.0

    eur_payout = await client.post(
        "/api/v1/affiliate/payout-requests",
        headers=affiliate_headers,
        json={"currency": "EUR"},
    )
    assert eur_payout.status_code == 200
    assert eur_payout.json()["requested_amount"] == 10.0

    rejected = await client.post(
        f"/api/v1/admin/payouts/{eur_payout.json()['id']}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert [item["to_status"] for item in rejected.json()["transitions"]] == [
        "pending_approval",
        "rejected",
    ]

    duplicate_rejection = await client.post(
        f"/api/v1/admin/payouts/{eur_payout.json()['id']}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert duplicate_rejection.status_code == 400

    balance = await client.get("/api/v1/affiliate/balance", headers=affiliate_headers)
    eur_balance = next(item for item in balance.json()["balances_by_currency"] if item["currency"] == "EUR")
    assert eur_balance["available"] == 10.0
    assert eur_balance["pending"] == 10.0

    retry_request = await client.post(
        "/api/v1/affiliate/payout-requests",
        headers=affiliate_headers,
        json={"currency": "EUR"},
    )
    assert retry_request.status_code == 200
    assert retry_request.json()["requested_amount"] == 10.0
