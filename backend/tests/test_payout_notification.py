"""Payout payout-notification delivery lifecycle.

`confirm_payout_payment` creates one ``pending`` PayoutNotification row in the
payment transaction; after commit a background task claims it (``sending`` +
lease + attempt_count), delivers the payout-paid email, and records ``sent``
or ``failed``. A crashed send is recovered by the daily maintenance job once
the lease expires, and merchants can retry a ``failed`` notification.
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, update

from app.core.security import hash_api_key, hash_password
from app.db.models import (
    Affiliate,
    AffiliateAccount,
    Payout,
    PayoutNotification,
    Tenant,
    TenantUser,
)
from app.db.session import async_session
from app.jobs import payout_maintenance
from app.services import payout_notification as notification_service
from app.services.payout_notification import deliver_payout_notification

PAST_DUE = date.today() - timedelta(days=10)
PAID_AT_PAST = datetime.now(timezone.utc) - timedelta(minutes=5)

CONFIRM_PAYLOAD = {
    "paid_at": PAID_AT_PAST.isoformat(),
    "transfer_reference": "PP-NOTIF-1",
}


def _admin_headers(payout_scenario) -> dict:
    return {"Authorization": f"Bearer {payout_scenario.admin_token}"}


async def _paid_payout_id(
    client: AsyncClient, payout_scenario, marker: str = "notif-1"
) -> str:
    commission_id = await payout_scenario.create_commission(
        PAST_DUE, marker, status="available"
    )
    request = await client.post(
        "/api/v1/affiliate/payout-requests",
        headers=payout_scenario.affiliate_headers,
        json={"currency": "USD", "commission_ids": [str(commission_id)]},
    )
    assert request.status_code == 200
    payout_id = request.json()["id"]
    admin = _admin_headers(payout_scenario)
    approved = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/approve", headers=admin
    )
    assert approved.status_code == 200
    confirmed = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers=admin,
        json=CONFIRM_PAYLOAD,
    )
    assert confirmed.status_code == 200
    return payout_id


async def _notification(payout_id: str) -> PayoutNotification:
    async with async_session() as db:
        row = await db.scalar(
            select(PayoutNotification).where(
                PayoutNotification.payout_id == uuid.UUID(payout_id)
            )
        )
        assert row is not None
        db.expunge(row)
        return row


def _stub_entrypoint(monkeypatch) -> list:
    """Replace the background send entrypoint with a recorder so the payment
    flow can be asserted without delivering email."""
    calls = []

    async def fake_send_task(payout_id):
        calls.append(payout_id)

    monkeypatch.setattr(
        notification_service, "send_payout_notification", fake_send_task
    )
    return calls


def _stub_sender(monkeypatch, calls: list | None = None, fail: dict | None = None):
    """Replace the provider-facing email sender used by the delivery worker."""

    async def fake_payout_email(*, to, affiliate_name, payout, payment):
        if calls is not None:
            calls.append({"to": to, "affiliate_name": affiliate_name})
        if fail and fail["enabled"]:
            raise RuntimeError(fail.get("message", "SES unavailable"))

    monkeypatch.setattr(
        notification_service, "send_payout_paid_email", fake_payout_email
    )


@pytest.mark.asyncio
async def test_payment_commit_creates_one_pending_notification(
    client: AsyncClient, payout_scenario, monkeypatch
):
    task_calls = _stub_entrypoint(monkeypatch)
    payout_id = await _paid_payout_id(client, payout_scenario, "notif-create")

    # The send task is enqueued after commit with only the payout id.
    assert task_calls == [uuid.UUID(payout_id)]

    notification = await _notification(payout_id)
    assert notification.status == "pending"
    assert notification.attempt_count == 0
    assert notification.lease_expires_at is None
    assert notification.sent_at is None


@pytest.mark.asyncio
async def test_repeated_confirmation_does_not_create_second_notification(
    client: AsyncClient, payout_scenario, monkeypatch
):
    _stub_entrypoint(monkeypatch)
    payout_id = await _paid_payout_id(client, payout_scenario, "notif-dup")

    replay = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/confirm-payment",
        headers=_admin_headers(payout_scenario),
        json=CONFIRM_PAYLOAD,
    )
    assert replay.status_code == 200

    async with async_session() as db:
        count = await db.scalar(
            select(func.count(PayoutNotification.id)).where(
                PayoutNotification.payout_id == uuid.UUID(payout_id)
            )
        )
    assert count == 1


@pytest.mark.asyncio
async def test_successful_send_marks_notification_sent(
    client: AsyncClient, payout_scenario, monkeypatch
):
    sends = []
    _stub_sender(monkeypatch, calls=sends)

    payout_id = await _paid_payout_id(client, payout_scenario, "notif-sent")

    # The background task ran inline: claimed, sent, lease cleared.
    notification = await _notification(payout_id)
    assert notification.status == "sent"
    assert notification.attempt_count == 1
    assert notification.sent_at is not None
    assert notification.last_attempt_at is not None
    assert notification.lease_expires_at is None
    assert notification.updated_at is not None

    assert sends == [
        {"to": "payout-scenario@example.com", "affiliate_name": "Payout Scenario Tester"}
    ]


@pytest.mark.asyncio
async def test_failed_send_marks_failed_and_payout_stays_paid(
    client: AsyncClient, payout_scenario, monkeypatch
):
    _stub_sender(monkeypatch, fail={"enabled": True, "message": "SES throttled"})

    payout_id = await _paid_payout_id(client, payout_scenario, "notif-fail")

    notification = await _notification(payout_id)
    assert notification.status == "failed"
    assert notification.attempt_count == 1
    assert "SES throttled" in notification.last_error
    assert notification.last_attempt_at is not None
    assert notification.lease_expires_at is None
    assert notification.sent_at is None

    # A failed send never reverts payment state, and the notification status
    # is visible on the tenant payout detail for retry.
    detail = await client.get(
        f"/api/v1/admin/payouts/{payout_id}",
        headers=_admin_headers(payout_scenario),
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "paid"
    assert detail.json()["payout_payment"]["transfer_reference"] == "PP-NOTIF-1"
    assert detail.json()["payout_notification"]["status"] == "failed"


@pytest.mark.asyncio
async def test_concurrent_workers_claim_a_notification_once(
    client: AsyncClient, payout_scenario, monkeypatch
):
    """Two racing delivery workers must not double-claim: the conditional
    UPDATE lets exactly one own the row."""
    _stub_entrypoint(monkeypatch)  # keep the row pending
    payout_id = await _paid_payout_id(client, payout_scenario, "notif-race")

    sends = []
    _stub_sender(monkeypatch, calls=sends)

    async def worker():
        async with async_session() as db:
            return await deliver_payout_notification(db, uuid.UUID(payout_id))

    outcomes = await asyncio.gather(worker(), worker())

    assert sorted(outcomes, key=lambda o: o or "") == [None, "sent"]
    assert len(sends) == 1

    notification = await _notification(payout_id)
    assert notification.status == "sent"
    assert notification.attempt_count == 1


@pytest.mark.asyncio
async def test_maintenance_job_recovers_expired_sending_lease(
    client: AsyncClient, payout_scenario, monkeypatch
):
    """A worker that crashes after claiming leaves a ``sending`` row whose
    lease eventually expires; the daily job claims and delivers it."""
    _stub_entrypoint(monkeypatch)  # keep the row pending
    payout_id = await _paid_payout_id(client, payout_scenario, "notif-lease")

    # Simulate a crashed worker: claimed but never completed.
    crashed_lease = datetime.now(timezone.utc) - timedelta(minutes=1)
    async with async_session() as db:
        await db.execute(
            update(PayoutNotification)
            .where(PayoutNotification.payout_id == uuid.UUID(payout_id))
            .values(
                status="sending",
                attempt_count=1,
                lease_expires_at=crashed_lease,
                last_attempt_at=crashed_lease,
                updated_at=crashed_lease,
            )
        )
        await db.commit()

    sends = []
    _stub_sender(monkeypatch, calls=sends)

    async def _no_commissions(db, now_utc=None):
        return 0

    monkeypatch.setattr(
        payout_maintenance, "mature_due_commissions", _no_commissions
    )
    summary = await payout_maintenance.run_maturity_job(async_session)

    assert summary["notifications"]["sent"] == 1
    assert len(sends) == 1

    notification = await _notification(payout_id)
    assert notification.status == "sent"
    assert notification.attempt_count == 2
    assert notification.sent_at is not None
    assert notification.lease_expires_at is None


@pytest.mark.asyncio
async def test_retry_notification_flips_failed_to_sent(
    client: AsyncClient, payout_scenario, monkeypatch
):
    fail = {"enabled": True, "message": "SES throttled"}
    sends = []
    _stub_sender(monkeypatch, calls=sends, fail=fail)

    payout_id = await _paid_payout_id(client, payout_scenario, "notif-retry")
    assert (await _notification(payout_id)).status == "failed"

    # Provider recovered: merchant retry requeues the notification and the
    # background task delivers it.
    fail["enabled"] = False
    response = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/retry-notification",
        headers=_admin_headers(payout_scenario),
    )

    assert response.status_code == 200
    assert response.json()["payout_notification"]["status"] == "pending"

    notification = await _notification(payout_id)
    assert notification.status == "sent"
    assert notification.attempt_count == 2
    assert notification.sent_at is not None
    assert len(sends) == 2


@pytest.mark.asyncio
async def test_retry_notification_rejects_non_retryable_states(
    client: AsyncClient, payout_scenario, monkeypatch
):
    admin = _admin_headers(payout_scenario)

    # A sent notification is not retryable.
    sends = []
    _stub_sender(monkeypatch, calls=sends)
    payout_id = await _paid_payout_id(client, payout_scenario, "notif-noretry")
    assert (await _notification(payout_id)).status == "sent"

    sent_retry = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/retry-notification",
        headers=admin,
    )
    assert sent_retry.status_code == 409

    # A payout that was never paid has nothing to retry.
    commission_id = await payout_scenario.create_commission(
        PAST_DUE, "notif-unpaid", status="available"
    )
    request = await client.post(
        "/api/v1/affiliate/payout-requests",
        headers=payout_scenario.affiliate_headers,
        json={"currency": "USD", "commission_ids": [str(commission_id)]},
    )
    unpaid_id = request.json()["id"]
    unpaid_retry = await client.post(
        f"/api/v1/admin/payouts/{unpaid_id}/retry-notification",
        headers=admin,
    )
    assert unpaid_retry.status_code == 409

    # Unknown payout ids get the usual 404.
    unknown = await client.post(
        f"/api/v1/admin/payouts/{uuid.uuid4()}/retry-notification",
        headers=admin,
    )
    assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_retry_notification_hides_other_tenants_payout(
    client: AsyncClient, payout_scenario, monkeypatch
):
    _stub_sender(monkeypatch, fail={"enabled": True})
    payout_id = await _paid_payout_id(client, payout_scenario, "notif-tenant")
    assert (await _notification(payout_id)).status == "failed"

    async with async_session() as db:
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
    foreign = await client.post(
        f"/api/v1/admin/payouts/{payout_id}/retry-notification",
        headers={"Authorization": f"Bearer {login.json()['token']}"},
    )
    # Same 404 as an unknown id: cross-tenant existence is never revealed.
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_affiliate_payout_detail_returns_lines_and_payment(
    client: AsyncClient, payout_scenario, monkeypatch
):
    """The emailed deep link lands on this endpoint: the authenticated
    affiliate sees their payout's commission lines and payment record."""
    _stub_sender(monkeypatch)
    payout_id = await _paid_payout_id(client, payout_scenario, "notif-detail")

    detail = await client.get(
        f"/api/v1/affiliate/payouts/{payout_id}",
        headers=payout_scenario.affiliate_headers,
    )

    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == payout_id
    assert body["status"] == "paid"
    assert body["payout_payment"]["transfer_reference"] == "PP-NOTIF-1"
    assert body["payout_payment"]["payment_method"] == "paypal"
    assert datetime.fromisoformat(body["payout_payment"]["paid_at"]) == PAID_AT_PAST
    assert len(body["payout_commissions"]) == 1
    assert body["payout_commissions"][0]["gross_amount"] == 10.0


@pytest.mark.asyncio
async def test_affiliate_payout_detail_scoped_to_owner(
    client: AsyncClient, payout_scenario, monkeypatch
):
    """Another affiliate's payout and foreign-tenant context both fail
    closed — the API, not the link's tenant_id, is the authorization
    boundary."""
    _stub_sender(monkeypatch)
    payout_id = await _paid_payout_id(client, payout_scenario, "notif-owner")

    async with async_session() as db:
        account = AffiliateAccount(
            email="sibling@example.com",
            password_hash="unused",
            name="Sibling Affiliate",
            country="US",
            tax_status="us_person",
        )
        db.add(account)
        await db.flush()
        sibling = Affiliate(
            affiliate_account_id=account.id,
            tenant_id=payout_scenario.tenant_id,
        )
        db.add(sibling)
        await db.commit()
        sibling_id = sibling.id

        other_payout = Payout(
            affiliate_id=sibling_id,
            tenant_id=payout_scenario.tenant_id,
            status="paid",
            currency="USD",
        )
        db.add(other_payout)
        await db.commit()
        other_payout_id = other_payout.id

    headers = payout_scenario.affiliate_headers
    for target in (str(other_payout_id), str(uuid.uuid4()), "not-a-uuid"):
        hidden = await client.get(
            f"/api/v1/affiliate/payouts/{target}", headers=headers
        )
        assert hidden.status_code == 404, target

    # A tenant id the affiliate is not linked to is rejected outright.
    foreign_tenant = await client.get(
        f"/api/v1/affiliate/payouts/{payout_id}",
        headers={
            "Authorization": headers["Authorization"],
            "X-Tenant-Id": str(uuid.uuid4()),
        },
    )
    assert foreign_tenant.status_code == 403
