import asyncio
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select, update

from app.db.models import (
    Affiliate,
    AffiliateAccount,
    Commission,
    Event,
    Payout,
    PayoutCommission,
    Tenant,
)
from app.db.session import async_session
from app.queue.handlers import handle_payout
from app.schemas.payout import PayoutRequest
from app.services.commission import mature_due_commissions, utc_midnight
from app.services.payout import request_payout


def test_payout_request_rejects_empty_commission_ids():
    with pytest.raises(ValidationError):
        PayoutRequest(currency="USD", commission_ids=[])


def test_payout_request_rejects_client_amount():
    with pytest.raises(ValidationError):
        PayoutRequest(currency="USD", amount=1)


def test_payout_request_rejects_duplicate_commission_ids():
    commission_id = uuid.uuid4()
    with pytest.raises(ValidationError):
        PayoutRequest(currency="USD", commission_ids=[commission_id, commission_id])


def test_payout_request_rejects_malformed_commission_ids():
    with pytest.raises(ValidationError):
        PayoutRequest(currency="USD", commission_ids=["not-a-uuid"])


def test_payout_request_without_ids_requests_all_available():
    request = PayoutRequest(currency="USD")
    assert request.commission_ids is None


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

    # No incoming-payment webhook call: the sale's merchant-provided
    # good_date alone controls when the commission becomes available.

    # A merchant due date comfortably in the future keeps this commission
    # pending. +2 days so local-tomorrow's UTC midnight is never already past
    # (local date can trail the UTC date in western timezones).
    eur_future_date = date.today() + timedelta(days=2)
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
            "good_date": str(eur_future_date),
            "payment_record_id": "payout-pay-eur",
        },
    )
    assert eur_sale.status_code == 200

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

    # mature due commissions the way the daily job does; request_payout no
    # longer promotes them lazily.
    async with async_session() as db:
        await mature_due_commissions(db)

    # Two concurrent requests for the same currency race on the same
    # available rows; FOR UPDATE serializes them so exactly one wins.
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
    assert by_currency["USD"][0]["status"] == "reserved"
    assert by_currency["USD"][0]["available_on"] == str(sale_date)
    assert sorted(item["status"] for item in by_currency["EUR"]) == ["available", "pending"]
    assert sorted(item["available_on"] for item in by_currency["EUR"]) == [
        str(sale_date),
        str(eur_future_date),
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

    # A stale SQS payout message drained by the worker is a no-op: it must
    # not dispatch a provider transfer or touch the payout/commissions.
    async with async_session() as db:
        await handle_payout(db, payout_id)
    approved_payout = await client.get(
        f"/api/v1/admin/payouts/{payout_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert approved_payout.json()["status"] == "approved"
    commissions = await client.get(
        "/api/v1/affiliate/commissions",
        headers=affiliate_headers,
    )
    assert next(
        c for c in commissions.json() if c["currency"] == "USD"
    )["status"] == "reserved"

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
    assert by_currency["USD"]["status"] == "reserved"

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
    assert eur_balance["reserved"] == 0.0

    eur_payout = await client.post(
        "/api/v1/affiliate/payout-requests",
        headers=affiliate_headers,
        json={"currency": "EUR"},
    )
    assert eur_payout.status_code == 200
    assert eur_payout.json()["requested_amount"] == 10.0

    balance = await client.get("/api/v1/affiliate/balance", headers=affiliate_headers)
    eur_balance = next(item for item in balance.json()["balances_by_currency"] if item["currency"] == "EUR")
    assert eur_balance["available"] == 0.0
    assert eur_balance["reserved"] == 10.0
    assert eur_balance["pending"] == 10.0

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
    assert eur_balance["reserved"] == 0.0

    retry_request = await client.post(
        "/api/v1/affiliate/payout-requests",
        headers=affiliate_headers,
        json={"currency": "EUR"},
    )
    assert retry_request.status_code == 200
    assert retry_request.json()["requested_amount"] == 10.0


PAST_DUE = date.today() - timedelta(days=10)


def _payout_request(client: AsyncClient, payout_scenario, payload: dict):
    return client.post(
        "/api/v1/affiliate/payout-requests",
        headers=payout_scenario.affiliate_headers,
        json=payload,
    )


async def _payout_count(payout_scenario) -> int:
    async with payout_scenario.db_session() as db:
        return await db.scalar(
            select(func.count(Payout.id)).where(
                Payout.affiliate_id == payout_scenario.affiliate_id
            )
        )


async def _create_foreign_commission(payout_scenario, payment_record_id: str):
    """An available commission owned by a different affiliate in the same tenant."""
    async with payout_scenario.db_session() as db:
        account = AffiliateAccount(
            email=f"foreign-{payment_record_id}@example.com",
            password_hash="unused",
            name="Foreign Affiliate",
            country="US",
            tax_status="us_person",
        )
        db.add(account)
        await db.flush()
        foreign = Affiliate(
            affiliate_account_id=account.id,
            tenant_id=payout_scenario.tenant_id,
        )
        db.add(foreign)
        await db.flush()
        event = Event(
            event_id=f"sale-{payment_record_id}",
            type="sale",
            tenant_id=payout_scenario.tenant_id,
            campaign_id=payout_scenario.campaign_id,
            affiliate_id=foreign.id,
            customer_id=f"cust-{payment_record_id}",
            amount=Decimal("100.00"),
            currency="USD",
            payment_sequence=1,
            good_date=PAST_DUE,
            payment_record_id=payment_record_id,
        )
        db.add(event)
        await db.flush()
        commission = Commission(
            event_id=event.id,
            affiliate_id=foreign.id,
            gross_amount=Decimal("10.00"),
            withholding_amount=Decimal("0.00"),
            net_amount=Decimal("10.00"),
            currency="USD",
            status="available",
            available_on=PAST_DUE,
            available_at=utc_midnight(PAST_DUE),
        )
        db.add(commission)
        await db.commit()
        return commission.id


@pytest.mark.asyncio
async def test_payout_without_ids_reserves_all_available_in_currency(
    client: AsyncClient, payout_scenario
):
    first = await payout_scenario.create_commission(
        PAST_DUE, "sel-all-1", status="available"
    )
    second = await payout_scenario.create_commission(
        PAST_DUE, "sel-all-2", status="available"
    )
    pending = await payout_scenario.create_commission(
        PAST_DUE, "sel-pending-1", status="pending"
    )

    response = await _payout_request(client, payout_scenario, {"currency": "USD"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_approval"
    assert body["requested_amount"] == 20.0
    assert body["withholding_total"] == 0.0
    assert body["net_paid"] == 20.0
    assert await payout_scenario.commission_status(first) == "reserved"
    assert await payout_scenario.commission_status(second) == "reserved"
    assert await payout_scenario.commission_status(pending) == "pending"


@pytest.mark.asyncio
async def test_payout_with_ids_reserves_only_selected(
    client: AsyncClient, payout_scenario
):
    first = await payout_scenario.create_commission(
        PAST_DUE, "sel-sub-1", status="available"
    )
    second = await payout_scenario.create_commission(
        PAST_DUE, "sel-sub-2", status="available"
    )
    left = await payout_scenario.create_commission(
        PAST_DUE, "sel-sub-3", status="available"
    )

    response = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(second), str(first)]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_approval"
    # Amounts are derived server-side from the selected commissions only.
    assert body["requested_amount"] == 20.0
    assert body["withholding_total"] == 0.0
    assert body["net_paid"] == 20.0

    assert await payout_scenario.commission_status(first) == "reserved"
    assert await payout_scenario.commission_status(second) == "reserved"
    assert await payout_scenario.commission_status(left) == "available"

    async with payout_scenario.db_session() as db:
        links = (
            await db.execute(
                select(PayoutCommission).where(
                    PayoutCommission.payout_id == uuid.UUID(body["id"])
                )
            )
        ).scalars().all()
    assert {link.commission_id for link in links} == {first, second}
    assert all(link.is_active for link in links)


@pytest.mark.asyncio
async def test_payout_with_unknown_ids_rejects_without_payout(
    client: AsyncClient, payout_scenario
):
    available_id = await payout_scenario.create_commission(
        PAST_DUE, "sel-unknown-1", status="available"
    )

    missing_only = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(uuid.uuid4())]},
    )
    assert missing_only.status_code == 409

    mixed = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(available_id), str(uuid.uuid4())]},
    )
    assert mixed.status_code == 409

    # Rejected selections must not create a payout or touch any commission.
    assert await _payout_count(payout_scenario) == 0
    assert await payout_scenario.commission_status(available_id) == "available"


@pytest.mark.asyncio
async def test_payout_with_foreign_affiliate_commission_rejects(
    client: AsyncClient, payout_scenario
):
    foreign_id = await _create_foreign_commission(payout_scenario, "sel-foreign-1")

    response = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(foreign_id)]},
    )

    assert response.status_code == 409
    assert await _payout_count(payout_scenario) == 0


@pytest.mark.asyncio
async def test_payout_with_wrong_currency_rejects(
    client: AsyncClient, payout_scenario
):
    commission_id = await payout_scenario.create_commission(
        PAST_DUE, "sel-eur-1", status="available"
    )
    async with payout_scenario.db_session() as db:
        await db.execute(
            update(Commission)
            .where(Commission.id == commission_id)
            .values(currency="EUR")
        )
        await db.commit()

    wrong_currency = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(commission_id)]},
    )
    assert wrong_currency.status_code == 409
    assert await _payout_count(payout_scenario) == 0
    assert await payout_scenario.commission_status(commission_id) == "available"

    right_currency = await _payout_request(
        client,
        payout_scenario,
        {"currency": "EUR", "commission_ids": [str(commission_id)]},
    )
    assert right_currency.status_code == 200
    assert right_currency.json()["requested_amount"] == 10.0


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["pending", "reserved", "paid", "reversed"])
async def test_payout_with_unavailable_status_rejects(
    client: AsyncClient, payout_scenario, status
):
    commission_id = await payout_scenario.create_commission(
        PAST_DUE, f"sel-{status}-1", status=status
    )

    response = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(commission_id)]},
    )

    assert response.status_code == 409
    assert await payout_scenario.commission_status(commission_id) == status
    assert await _payout_count(payout_scenario) == 0


@pytest.mark.asyncio
async def test_concurrent_payouts_for_same_commission_reserve_once(
    client: AsyncClient, payout_scenario
):
    commission_id = await payout_scenario.create_commission(
        PAST_DUE, "sel-race-1", status="available"
    )

    responses = await asyncio.gather(
        _payout_request(
            client,
            payout_scenario,
            {"currency": "USD", "commission_ids": [str(commission_id)]},
        ),
        _payout_request(
            client,
            payout_scenario,
            {"currency": "USD", "commission_ids": [str(commission_id)]},
        ),
    )

    # The loser waits on the row lock, then sees the reservation taken.
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert await payout_scenario.commission_status(commission_id) == "reserved"
    assert await _payout_count(payout_scenario) == 1


@pytest.mark.asyncio
async def test_rejection_releases_commission_for_a_new_payout(
    client: AsyncClient, payout_scenario
):
    commission_id = await payout_scenario.create_commission(
        PAST_DUE, "sel-release-1", status="available"
    )
    admin_headers = {"Authorization": f"Bearer {payout_scenario.admin_token}"}

    first = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(commission_id)]},
    )
    assert first.status_code == 200
    first_payout_id = first.json()["id"]

    rejected = await client.post(
        f"/api/v1/admin/payouts/{first_payout_id}/reject",
        headers=admin_headers,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert await payout_scenario.commission_status(commission_id) == "available"

    # Rejecting again is a no-op guard, not a second release.
    duplicate = await client.post(
        f"/api/v1/admin/payouts/{first_payout_id}/reject",
        headers=admin_headers,
    )
    assert duplicate.status_code == 400

    second = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(commission_id)]},
    )
    assert second.status_code == 200
    second_payout_id = second.json()["id"]
    assert second_payout_id != first_payout_id
    assert await payout_scenario.commission_status(commission_id) == "reserved"

    # The old association is kept inactive for history; the new payout holds
    # the only active link.
    async with payout_scenario.db_session() as db:
        links = (
            await db.execute(
                select(PayoutCommission).where(
                    PayoutCommission.commission_id == commission_id
                )
            )
        ).scalars().all()
    assert len(links) == 2
    by_payout = {str(link.payout_id): link for link in links}
    assert by_payout[first_payout_id].is_active is False
    assert by_payout[second_payout_id].is_active is True


@pytest.mark.asyncio
async def test_request_payout_empty_commission_ids_rejects(payout_scenario):
    """An explicit empty selection only slips past the request schema on
    direct service calls; the service must still refuse a $0 payout with
    no links."""
    async with payout_scenario.db_session() as db:
        affiliate = await db.get(Affiliate, payout_scenario.affiliate_id)
        with pytest.raises(HTTPException) as excinfo:
            await request_payout(db, affiliate, "USD", [])
    assert excinfo.value.status_code == 400
    assert await _payout_count(payout_scenario) == 0


@pytest.mark.asyncio
async def test_request_payout_active_link_conflict_returns_409(
    client: AsyncClient, payout_scenario
):
    """A commission still stored 'available' but already holding an active
    link (a reservation race that outran the row lock) trips the partial
    unique index; that IntegrityError must surface as 409, not 500."""
    commission_id = await payout_scenario.create_commission(
        PAST_DUE, "sel-index-race-1", status="available"
    )
    await payout_scenario.add_legacy_active_payout(
        commission_id, payout_status="pending_approval", is_active=True
    )

    response = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(commission_id)]},
    )

    # The commission passes the availability count check because it is
    # stored 'available', so this 409 can only come from the unique index.
    assert response.status_code == 409
    assert await payout_scenario.commission_status(commission_id) == "available"
    assert await _payout_count(payout_scenario) == 1


@pytest.mark.asyncio
async def test_reject_releases_backfilled_pending_reservation(
    client: AsyncClient, payout_scenario
):
    """Migration e8f9a0b1c2d3 backfilled is_active=TRUE on links of
    in-flight payouts without rewriting commission.status, leaving the
    shape (active link, commission 'pending'). Rejection must release it."""
    commission_id = await payout_scenario.create_commission(
        PAST_DUE, "migrated-reject-1", status="pending"
    )
    payout_id = await payout_scenario.add_legacy_active_payout(
        commission_id, payout_status="pending_approval", is_active=True
    )

    rejected = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/reject",
        headers={"Authorization": f"Bearer {payout_scenario.admin_token}"},
    )

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert await payout_scenario.commission_status(commission_id) == "available"
    async with payout_scenario.db_session() as db:
        link = await db.scalar(
            select(PayoutCommission).where(PayoutCommission.payout_id == payout_id)
        )
    assert link.is_active is False


@pytest.mark.asyncio
async def test_confirm_payment_settles_backfilled_pending_reservation(
    client: AsyncClient, payout_scenario
):
    """The same backfilled shape must settle normally: approve then
    confirm-payment lands the commission on 'paid' with its link inactive."""
    commission_id = await payout_scenario.create_commission(
        PAST_DUE, "migrated-pay-1", status="pending"
    )
    payout_id = await payout_scenario.add_legacy_active_payout(
        commission_id, payout_status="pending_approval", is_active=True
    )
    admin_headers = {"Authorization": f"Bearer {payout_scenario.admin_token}"}

    approved = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/approve",
        headers=admin_headers,
    )
    assert approved.status_code == 200

    confirmed = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers=admin_headers,
        json={
            "payment_method": "bank_transfer",
            "transfer_reference": "migrated-tx-1",
        },
    )

    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "paid"
    assert await payout_scenario.commission_status(commission_id) == "paid"
    async with payout_scenario.db_session() as db:
        link = await db.scalar(
            select(PayoutCommission).where(PayoutCommission.payout_id == payout_id)
        )
    assert link.is_active is False
