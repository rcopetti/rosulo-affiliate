import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select, update

from app.core.security import hash_api_key, hash_password
from app.db.models import (
    Affiliate,
    AffiliateAccount,
    Commission,
    Event,
    Payout,
    PayoutCommission,
    PayoutNotification,
    PayoutPayment,
    Tenant,
    TenantUser,
)
from app.db.session import async_session
from app.queue.handlers import handle_payout
from app.schemas.payout import PayoutPaymentConfirmation, PayoutRequest
from app.services.commission import mature_due_commissions, utc_midnight
from app.services.payout import _rolling_year_start, request_payout


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


PAID_AT_PAST = datetime.now(timezone.utc) - timedelta(minutes=5)


def test_payment_confirmation_requires_paid_at_and_reference():
    with pytest.raises(ValidationError):
        PayoutPaymentConfirmation(transfer_reference="tx-1")
    with pytest.raises(ValidationError):
        PayoutPaymentConfirmation(paid_at=PAID_AT_PAST.isoformat())


def test_payment_confirmation_rejects_naive_paid_at():
    with pytest.raises(ValidationError):
        PayoutPaymentConfirmation(
            paid_at="2026-09-01T10:00:00", transfer_reference="tx-1"
        )


def test_payment_confirmation_rejects_future_paid_at():
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with pytest.raises(ValidationError):
        PayoutPaymentConfirmation(paid_at=future, transfer_reference="tx-1")


def test_payment_confirmation_requires_nonblank_reference():
    with pytest.raises(ValidationError):
        PayoutPaymentConfirmation(
            paid_at=PAID_AT_PAST.isoformat(), transfer_reference="   "
        )


@pytest.mark.parametrize("field", ["amount", "currency", "payment_method"])
def test_payment_confirmation_rejects_client_overrides(field):
    """Amount/currency/method are server-derived; the client must not set them."""
    with pytest.raises(ValidationError):
        PayoutPaymentConfirmation(
            paid_at=PAID_AT_PAST.isoformat(),
            transfer_reference="tx-1",
            **{field: "override"},
        )


def test_payment_confirmation_trims_reference_and_keeps_offset():
    confirmation = PayoutPaymentConfirmation(
        paid_at=PAID_AT_PAST.isoformat(), transfer_reference="  PP-TX-1  "
    )
    assert confirmation.transfer_reference == "PP-TX-1"
    assert confirmation.paid_at == PAID_AT_PAST


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
    assert "available_on" not in by_currency["USD"][0]
    assert datetime.fromisoformat(
        by_currency["USD"][0]["available_at"]
    ) == utc_midnight(sale_date)
    assert sorted(item["status"] for item in by_currency["EUR"]) == ["available", "pending"]
    assert sorted(
        datetime.fromisoformat(item["available_at"])
        for item in by_currency["EUR"]
    ) == [utc_midnight(sale_date), utc_midnight(eur_future_date)]

    premature_payment = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "paid_at": PAID_AT_PAST.isoformat(),
            "transfer_reference": "bank-tx-123",
        },
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
        "paid_at": PAID_AT_PAST.isoformat(),
        "transfer_reference": "bank-tx-123",
    }
    confirmed = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payment_details,
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "paid"
    assert "payment_record" not in confirmed.json()
    assert confirmed.json()["payout_payment"]["payment_method"] == "paypal"
    assert confirmed.json()["payout_payment"]["transfer_reference"] == "bank-tx-123"
    assert confirmed.json()["payout_payment"]["amount"] == confirmed.json()["net_paid"]
    assert confirmed.json()["payout_payment"]["currency"] == confirmed.json()["currency"]
    assert datetime.fromisoformat(
        confirmed.json()["payout_payment"]["paid_at"]
    ) == PAID_AT_PAST
    assert datetime.fromisoformat(confirmed.json()["paid_at"]) == PAID_AT_PAST
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
    assert duplicate_confirmation.json()["payout_payment"]["id"] == confirmed.json()["payout_payment"]["id"]

    conflicting_confirmation = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "paid_at": PAID_AT_PAST.isoformat(),
            "transfer_reference": "different-ref",
        },
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
            "paid_at": PAID_AT_PAST.isoformat(),
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


async def _approved_payout_id(
    client: AsyncClient, payout_scenario, marker: str
) -> str:
    """Create one available commission, request a payout for it, and approve."""
    commission_id = await payout_scenario.create_commission(
        PAST_DUE, marker, status="available"
    )
    request = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(commission_id)]},
    )
    assert request.status_code == 200
    payout_id = request.json()["id"]
    approved = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/approve",
        headers={"Authorization": f"Bearer {payout_scenario.admin_token}"},
    )
    assert approved.status_code == 200
    return payout_id


def _confirm_payload(**overrides) -> dict:
    payload = {
        "paid_at": PAID_AT_PAST.isoformat(),
        "transfer_reference": "PP-TX-1",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_confirm_payment_records_paypal_payment(
    client: AsyncClient, payout_scenario, monkeypatch
):
    # Stub the post-commit send so this test asserts the committed
    # notification row, not the delivery outcome (covered in
    # test_payout_notification.py).
    async def _no_send(payout_id):
        return None

    monkeypatch.setattr(
        "app.services.payout_notification.send_payout_notification", _no_send
    )
    payout_id = await _approved_payout_id(client, payout_scenario, "confirm-1")
    admin_headers = {"Authorization": f"Bearer {payout_scenario.admin_token}"}

    confirmed = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers=admin_headers,
        json=_confirm_payload(transfer_reference="  PP-TX-100  "),
    )

    assert confirmed.status_code == 200
    body = confirmed.json()
    assert body["status"] == "paid"
    assert "payment_record" not in body
    payment = body["payout_payment"]
    assert payment["payment_method"] == "paypal"
    assert payment["amount"] == body["net_paid"] == 10.0
    assert payment["currency"] == body["currency"] == "USD"
    assert payment["transfer_reference"] == "PP-TX-100"
    assert datetime.fromisoformat(payment["paid_at"]) == PAID_AT_PAST
    assert datetime.fromisoformat(body["paid_at"]) == PAID_AT_PAST
    assert payment["recorded_by_tenant_user_id"]
    assert [item["to_status"] for item in body["transitions"]][-2:] == [
        "approved",
        "paid",
    ]

    # The payment row and its pending notification commit atomically.
    async with payout_scenario.db_session() as db:
        payment_row = await db.scalar(
            select(PayoutPayment).where(
                PayoutPayment.payout_id == uuid.UUID(payout_id)
            )
        )
        notification = await db.scalar(
            select(PayoutNotification).where(
                PayoutNotification.payout_id == uuid.UUID(payout_id)
            )
        )
    assert payment_row.payment_method == "paypal"
    assert payment_row.transfer_reference == "PP-TX-100"
    assert payment_row.paid_at == PAID_AT_PAST
    assert notification.status == "pending"
    assert notification.attempt_count == 0


@pytest.mark.asyncio
async def test_confirm_payment_identical_retry_returns_existing(
    client: AsyncClient, payout_scenario
):
    payout_id = await _approved_payout_id(client, payout_scenario, "confirm-retry-1")
    admin_headers = {"Authorization": f"Bearer {payout_scenario.admin_token}"}
    payload = _confirm_payload(transfer_reference="PP-TX-RETRY")

    first = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers=admin_headers,
        json=payload,
    )
    second = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers=admin_headers,
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        second.json()["payout_payment"]["id"]
        == first.json()["payout_payment"]["id"]
    )

    async with payout_scenario.db_session() as db:
        payment_count = await db.scalar(
            select(func.count(PayoutPayment.id)).where(
                PayoutPayment.payout_id == uuid.UUID(payout_id)
            )
        )
        notification_count = await db.scalar(
            select(func.count(PayoutNotification.id)).where(
                PayoutNotification.payout_id == uuid.UUID(payout_id)
            )
        )
    assert payment_count == 1
    assert notification_count == 1


@pytest.mark.asyncio
async def test_confirm_payment_retry_matches_same_instant_in_another_offset(
    client: AsyncClient, payout_scenario
):
    payout_id = await _approved_payout_id(client, payout_scenario, "confirm-retry-2")
    admin_headers = {"Authorization": f"Bearer {payout_scenario.admin_token}"}

    first = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers=admin_headers,
        json=_confirm_payload(),
    )
    same_instant = PAID_AT_PAST.astimezone(timezone(timedelta(hours=5, minutes=30)))
    second = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers=admin_headers,
        json=_confirm_payload(paid_at=same_instant.isoformat()),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert (
        second.json()["payout_payment"]["id"]
        == first.json()["payout_payment"]["id"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "conflict",
    [
        {"transfer_reference": "different-ref"},
        {"paid_at": (PAID_AT_PAST - timedelta(hours=1)).isoformat()},
    ],
)
async def test_confirm_payment_conflicting_retry_returns_409(
    client: AsyncClient, payout_scenario, conflict
):
    payout_id = await _approved_payout_id(client, payout_scenario, "confirm-409")
    admin_headers = {"Authorization": f"Bearer {payout_scenario.admin_token}"}
    payload = _confirm_payload()

    first = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers=admin_headers,
        json=payload,
    )
    assert first.status_code == 200

    conflicting = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers=admin_headers,
        json=_confirm_payload(**conflict),
    )
    assert conflicting.status_code == 409

    # The 409 must not mutate the stored payment or payout state.
    payout = await client.get(
        f"/api/v1/admin/payouts/{payout_id}",
        headers=admin_headers,
    )
    assert payout.json()["status"] == "paid"
    assert (
        payout.json()["payout_payment"]["id"]
        == first.json()["payout_payment"]["id"]
    )
    assert payout.json()["payout_payment"]["transfer_reference"] == "PP-TX-1"
    async with payout_scenario.db_session() as db:
        payment_count = await db.scalar(
            select(func.count(PayoutPayment.id)).where(
                PayoutPayment.payout_id == uuid.UUID(payout_id)
            )
        )
    assert payment_count == 1


@pytest.mark.asyncio
async def test_confirm_payment_requires_approved_status(
    client: AsyncClient, payout_scenario
):
    commission_id = await payout_scenario.create_commission(
        PAST_DUE, "confirm-status-1", status="available"
    )
    request = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(commission_id)]},
    )
    assert request.status_code == 200
    payout_id = request.json()["id"]
    admin_headers = {"Authorization": f"Bearer {payout_scenario.admin_token}"}

    # A payout still awaiting approval cannot be confirmed.
    pending = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers=admin_headers,
        json=_confirm_payload(),
    )
    assert pending.status_code == 400
    assert await payout_scenario.commission_status(commission_id) == "reserved"

    rejected = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/reject",
        headers=admin_headers,
    )
    assert rejected.status_code == 200

    # A rejected payout cannot be confirmed either.
    rejected_confirmation = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers=admin_headers,
        json=_confirm_payload(),
    )
    assert rejected_confirmation.status_code == 400


@pytest.mark.asyncio
async def test_confirm_payment_endpoint_validates_payload(
    client: AsyncClient, payout_scenario
):
    payout_id = await _approved_payout_id(client, payout_scenario, "confirm-422")
    admin_headers = {"Authorization": f"Bearer {payout_scenario.admin_token}"}
    url = f"/api/v1/admin/payouts/{payout_id}/confirm-payment"

    bad_payloads = [
        # naive paid_at: no timezone offset
        _confirm_payload(paid_at="2026-01-01T10:00:00"),
        # future paid_at
        _confirm_payload(
            paid_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        ),
        # blank transfer reference
        _confirm_payload(transfer_reference="   "),
        # client-supplied overrides are forbidden
        _confirm_payload(payment_method="bank_transfer"),
        _confirm_payload(amount="1.00"),
        _confirm_payload(currency="EUR"),
    ]
    for bad in bad_payloads:
        response = await client.post(url, headers=admin_headers, json=bad)
        assert response.status_code == 422, bad

    # Validation failures leave the payout approved and unrecorded.
    payout = await client.get(url.rsplit("/confirm-payment", 1)[0], headers=admin_headers)
    assert payout.json()["status"] == "approved"
    assert payout.json()["payout_payment"] is None


DETAIL_SALE_FIRST = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
DETAIL_SALE_SECOND = datetime(2026, 9, 25, 8, 30, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_payout_detail_returns_itemized_commissions_and_payee(
    client: AsyncClient, payout_scenario
):
    first = await payout_scenario.create_commission(
        PAST_DUE, "detail-1", status="available"
    )
    second = await payout_scenario.create_commission(
        PAST_DUE - timedelta(days=3), "detail-2", status="available"
    )

    # Pin distinct source-sale timestamps and sequences so the returned
    # window/line fields are verifiable rather than all "now".
    async with payout_scenario.db_session() as db:
        events = (
            await db.execute(
                select(Event).where(
                    Event.event_id.in_(["sale-detail-1", "sale-detail-2"])
                )
            )
        ).scalars().all()
        by_key = {event.event_id: event for event in events}
        by_key["sale-detail-1"].occurred_at = DETAIL_SALE_FIRST
        by_key["sale-detail-1"].payment_sequence = 1
        by_key["sale-detail-2"].occurred_at = DETAIL_SALE_SECOND
        by_key["sale-detail-2"].payment_sequence = 2
        await db.commit()
        event_row_ids = {key: str(event.id) for key, event in by_key.items()}

    request = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(first), str(second)]},
    )
    assert request.status_code == 200
    payout_id = request.json()["id"]

    detail = await client.get(
        f"/api/v1/admin/payouts/{payout_id}",
        headers={"Authorization": f"Bearer {payout_scenario.admin_token}"},
    )

    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "pending_approval"
    assert "paypal_batch_id" not in body
    assert "payment_record" not in body

    # Payee identity comes from the affiliate's account record.
    assert body["affiliate"]["name"] == "Payout Scenario Tester"
    assert body["affiliate"]["email"] == "payout-scenario@example.com"
    assert body["affiliate"]["paypal_email"] == "payout-scenario@example.com"

    lines = body["payout_commissions"]
    assert body["commission_count"] == 2
    assert len(lines) == 2
    by_commission = {line["commission_id"]: line for line in lines}
    assert set(by_commission) == {str(first), str(second)}

    first_line = by_commission[str(first)]
    assert first_line["event_id"] == event_row_ids["sale-detail-1"]
    assert datetime.fromisoformat(first_line["occurred_at"]) == DETAIL_SALE_FIRST
    assert first_line["good_date"] == str(PAST_DUE)
    assert first_line["payment_sequence"] == 1
    assert first_line["sale_amount"] == 100.0
    assert first_line["sale_payment_record_id"] == "detail-1"
    assert first_line["rate_percent"] == 10.0
    assert first_line["gross_amount"] == 10.0
    assert first_line["withholding_amount"] == 0.0
    assert first_line["net_amount"] == 10.0
    assert first_line["currency"] == "USD"
    assert first_line["campaign_id"] == str(payout_scenario.campaign_id)

    second_line = by_commission[str(second)]
    assert second_line["event_id"] == event_row_ids["sale-detail-2"]
    assert datetime.fromisoformat(second_line["occurred_at"]) == DETAIL_SALE_SECOND
    assert second_line["good_date"] == str(PAST_DUE - timedelta(days=3))
    assert second_line["payment_sequence"] == 2

    # Lines reconcile to the payout totals and the source-sale window.
    assert sum(line["gross_amount"] for line in lines) == body["requested_amount"]
    assert sum(line["withholding_amount"] for line in lines) == body["withholding_total"]
    assert sum(line["net_amount"] for line in lines) == body["net_paid"]
    assert datetime.fromisoformat(body["earliest_sale_at"]) == DETAIL_SALE_FIRST
    assert datetime.fromisoformat(body["latest_sale_at"]) == DETAIL_SALE_SECOND
    assert body["total_sale_amount"] == 200.0


@pytest.mark.asyncio
async def test_payout_detail_unknown_payout_returns_404(
    client: AsyncClient, payout_scenario
):
    response = await client.get(
        f"/api/v1/admin/payouts/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {payout_scenario.admin_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_payout_detail_hides_other_tenants_payout(
    client: AsyncClient, payout_scenario
):
    commission_id = await payout_scenario.create_commission(
        PAST_DUE, "detail-iso-1", status="available"
    )
    request = await _payout_request(
        client,
        payout_scenario,
        {"currency": "USD", "commission_ids": [str(commission_id)]},
    )
    assert request.status_code == 200
    payout_id = request.json()["id"]

    async with payout_scenario.db_session() as db:
        other_tenant = Tenant(
            name="other-co", api_key_hash=hash_api_key("other-key")
        )
        db.add(other_tenant)
        await db.flush()
        db.add(
            TenantUser(
                tenant_id=other_tenant.id,
                email="admin@other.co",
                password_hash=hash_password("admin123"),
                name="Other Admin",
                role="admin",
            )
        )
        await db.commit()

    login = await client.post(
        "/api/v1/auth/tenant/login",
        json={"email": "admin@other.co", "password": "admin123"},
    )
    assert login.status_code == 200

    foreign = await client.get(
        f"/api/v1/admin/payouts/{payout_id}",
        headers={"Authorization": f"Bearer {login.json()['token']}"},
    )
    # Same 404 as an unknown ID: cross-tenant existence is never revealed.
    assert foreign.status_code == 404


def test_rolling_year_start_handles_leap_day():
    assert _rolling_year_start(datetime(2028, 2, 29, 12, 0, tzinfo=timezone.utc)) == datetime(
        2027, 2, 28, 12, 0, tzinfo=timezone.utc
    )
    assert _rolling_year_start(datetime(2026, 10, 1, 8, 30, tzinfo=timezone.utc)) == datetime(
        2025, 10, 1, 8, 30, tzinfo=timezone.utc
    )


async def _seed_payout(
    payout_scenario,
    *,
    status="pending_approval",
    currency="USD",
    amount=Decimal("10.00"),
    requested_at=None,
    paid_at=None,
    reference="PP-REF",
    affiliate_id=None,
    tenant_id=None,
) -> uuid.UUID:
    """Insert a payout (plus its PayoutPayment when ``paid_at`` is given)
    directly, so tests can pin payment dates across aggregation windows
    that the confirm endpoint's not-in-the-future rule cannot express."""
    async with payout_scenario.db_session() as db:
        reviewer_id = await db.scalar(
            select(TenantUser.id).where(
                TenantUser.tenant_id == payout_scenario.tenant_id
            )
        )
        payout = Payout(
            affiliate_id=affiliate_id or payout_scenario.affiliate_id,
            tenant_id=tenant_id or payout_scenario.tenant_id,
            requested_amount=amount,
            approved_amount=amount,
            net_paid=amount,
            currency=currency,
            status=status,
            requested_at=requested_at or datetime.now(timezone.utc),
            paid_at=paid_at,
        )
        db.add(payout)
        await db.flush()
        if paid_at is not None:
            db.add(
                PayoutPayment(
                    payout_id=payout.id,
                    amount=amount,
                    currency=currency,
                    payment_method="paypal",
                    transfer_reference=reference,
                    paid_at=paid_at,
                    recorded_by_tenant_user_id=reviewer_id,
                )
            )
        await db.commit()
        return payout.id


def _affiliate_payouts_url(affiliate_id) -> str:
    return f"/api/v1/admin/affiliates/{affiliate_id}/payouts"


@pytest.mark.asyncio
async def test_affiliate_payout_history_paid_totals_by_currency(
    client: AsyncClient, payout_scenario
):
    now = datetime.now(timezone.utc)
    rolling_start = _rolling_year_start(now)
    ytd_start = datetime(now.year, 1, 1, tzinfo=timezone.utc)

    requested_base = now - timedelta(days=5)
    # USD payments spanning every aggregation window.
    await _seed_payout(
        payout_scenario,
        status="paid",
        amount=Decimal("10.00"),
        requested_at=requested_base,
        paid_at=now - timedelta(hours=1),
        reference="pp-usd-recent",
    )
    # Dec 31 of last year: inside the rolling 12 months (it is never
    # earlier than now-minus-one-year) but outside the current year.
    await _seed_payout(
        payout_scenario,
        status="paid",
        amount=Decimal("20.00"),
        requested_at=requested_base + timedelta(hours=1),
        paid_at=ytd_start - timedelta(days=1),
        reference="pp-usd-prior-year",
    )
    # Older than one year ago: excluded from both windows.
    await _seed_payout(
        payout_scenario,
        status="paid",
        amount=Decimal("40.00"),
        requested_at=requested_base + timedelta(hours=2),
        paid_at=rolling_start - timedelta(days=1),
        reference="pp-usd-old",
    )
    # A second currency must never be summed into USD.
    await _seed_payout(
        payout_scenario,
        status="paid",
        currency="EUR",
        amount=Decimal("7.50"),
        requested_at=requested_base + timedelta(hours=3),
        paid_at=now - timedelta(hours=2),
        reference="pp-eur-recent",
    )
    # Unpaid payouts appear in the history but never add to paid totals.
    for index, status in enumerate(("pending_approval", "approved", "rejected")):
        await _seed_payout(
            payout_scenario,
            status=status,
            requested_at=requested_base + timedelta(hours=4 + index),
        )

    response = await client.get(
        _affiliate_payouts_url(payout_scenario.affiliate_id),
        headers={"Authorization": f"Bearer {payout_scenario.admin_token}"},
        params={"limit": 20, "offset": 0},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 7
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert len(body["items"]) == 7

    totals = {row["currency"]: row for row in body["paid_totals_by_currency"]}
    assert set(totals) == {"USD", "EUR"}
    assert totals["USD"]["rolling_12_months"] == 30.0
    assert totals["USD"]["year_to_date"] == 10.0
    assert totals["EUR"]["rolling_12_months"] == 7.5
    assert totals["EUR"]["year_to_date"] == 7.5

    by_reference = {
        item.get("payment_reference"): item for item in body["items"]
    }
    paid_item = by_reference["pp-usd-recent"]
    assert paid_item["status"] == "paid"
    assert paid_item["requested_amount"] == 10.0
    assert paid_item["net_paid"] == 10.0
    assert paid_item["currency"] == "USD"
    assert datetime.fromisoformat(paid_item["paid_at"]) == now - timedelta(
        hours=1
    )
    unpaid_items = [item for item in body["items"] if item["status"] != "paid"]
    assert {item["status"] for item in unpaid_items} == {
        "pending_approval",
        "approved",
        "rejected",
    }
    assert all(item["payment_reference"] is None for item in unpaid_items)


@pytest.mark.asyncio
async def test_affiliate_payout_history_paginates_newest_first(
    client: AsyncClient, payout_scenario
):
    base = datetime.now(timezone.utc) - timedelta(days=30)
    ids = []
    for index in range(3):
        ids.append(
            await _seed_payout(
                payout_scenario,
                status="paid",
                requested_at=base + timedelta(hours=index),
                paid_at=base + timedelta(hours=index),
                reference=f"pp-page-{index}",
            )
        )

    admin = {"Authorization": f"Bearer {payout_scenario.admin_token}"}
    url = _affiliate_payouts_url(payout_scenario.affiliate_id)

    first_page = await client.get(
        url, headers=admin, params={"limit": 2, "offset": 0}
    )
    assert first_page.status_code == 200
    body = first_page.json()
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert [item["id"] for item in body["items"]] == [str(ids[2]), str(ids[1])]
    assert body["items"][0]["payment_reference"] == "pp-page-2"

    second_page = await client.get(
        url, headers=admin, params={"limit": 2, "offset": 2}
    )
    assert second_page.status_code == 200
    assert [item["id"] for item in second_page.json()["items"]] == [str(ids[0])]

    # Pagination bounds are validated: limit caps at 100, offset >= 0.
    for params in ({"limit": 101}, {"limit": 0}, {"offset": -1}):
        invalid = await client.get(url, headers=admin, params=params)
        assert invalid.status_code == 422, params


@pytest.mark.asyncio
async def test_affiliate_payout_history_scoped_to_tenant_and_affiliate(
    client: AsyncClient, payout_scenario
):
    admin = {"Authorization": f"Bearer {payout_scenario.admin_token}"}
    now = datetime.now(timezone.utc)

    async with payout_scenario.db_session() as db:
        other_tenant = Tenant(
            name="other-co", api_key_hash=hash_api_key("other-key")
        )
        db.add(other_tenant)
        await db.flush()
        other_account = AffiliateAccount(
            email="foreign-affiliate@example.com",
            password_hash="unused",
            name="Foreign Affiliate",
            country="US",
            tax_status="us_person",
        )
        db.add(other_account)
        await db.flush()
        other_affiliate = Affiliate(
            affiliate_account_id=other_account.id,
            tenant_id=other_tenant.id,
        )
        db.add(other_affiliate)
        sibling_account = AffiliateAccount(
            email="sibling-affiliate@example.com",
            password_hash="unused",
            name="Sibling Affiliate",
            country="US",
            tax_status="us_person",
        )
        db.add(sibling_account)
        await db.flush()
        sibling_affiliate = Affiliate(
            affiliate_account_id=sibling_account.id,
            tenant_id=payout_scenario.tenant_id,
        )
        db.add(sibling_affiliate)
        await db.commit()
        other_affiliate_id = other_affiliate.id
        sibling_affiliate_id = sibling_affiliate.id

    # Paid payouts belonging to a same-tenant sibling and to another
    # tenant's affiliate must not leak into this affiliate's history.
    await _seed_payout(
        payout_scenario,
        status="paid",
        amount=Decimal("99.00"),
        paid_at=now - timedelta(hours=1),
        reference="pp-sibling",
        affiliate_id=sibling_affiliate_id,
    )
    await _seed_payout(
        payout_scenario,
        status="paid",
        amount=Decimal("55.00"),
        paid_at=now - timedelta(hours=1),
        reference="pp-foreign",
        affiliate_id=other_affiliate_id,
        tenant_id=other_tenant.id,
    )
    own = await _seed_payout(
        payout_scenario,
        status="paid",
        paid_at=now - timedelta(hours=1),
        reference="pp-own",
    )

    response = await client.get(
        _affiliate_payouts_url(payout_scenario.affiliate_id),
        headers=admin,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [str(own)]
    totals = {row["currency"]: row for row in body["paid_totals_by_currency"]}
    assert totals["USD"]["rolling_12_months"] == 10.0
    assert totals["USD"]["year_to_date"] == 10.0

    # Missing, malformed, and cross-tenant affiliate IDs all return 404.
    for target in (uuid.uuid4(), other_affiliate_id, "not-a-uuid"):
        hidden = await client.get(_affiliate_payouts_url(target), headers=admin)
        assert hidden.status_code == 404, target
