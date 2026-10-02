import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core import money
from app.core.security import hash_api_key
from app.db.models import (
    Affiliate,
    AffiliateAccount,
    Campaign,
    Commission,
    Contract,
    Event,
    Tenant,
    Term,
)
from app.db.session import async_session
from app.schemas.event import EventCreate
from app.services.commission import mature_due_commissions


@pytest.mark.asyncio
async def test_event_ingestion(
    client: AsyncClient, tenant: Tenant, tenant_user, monkeypatch
):
    admin_login = await client.post(
        "/api/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "event@example.com"},
    )
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/api/v1/auth/affiliate/accept-invite",
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
        "/api/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Event Camp", "landing_url": "https://allbum.me/e"},
    )
    campaign_id = camp.json()["id"]

    click = await client.post(
        "/api/v1/events",
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

    sale_payload = {
        "event_id": "sale-1",
        "type": "sale",
        "campaign_id": campaign_id,
        "customer_id": "cust-1",
        "amount": 100.0,
        "currency": "USD",
        "payment_sequence": 1,
        "good_date": "2026-09-09",
        "payment_record_id": "pay-1",
    }
    sale = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json=sale_payload,
    )
    assert sale.status_code == 200
    assert sale.json()["type"] == "sale"

    retry = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json=sale_payload,
    )
    assert retry.status_code == 200
    assert retry.json()["id"] == sale.json()["id"]

    async with async_session() as db:
        commission_count = await db.scalar(
            select(func.count(Commission.id)).where(
                Commission.event_id == uuid.UUID(sale.json()["id"])
            )
        )
    assert commission_count == 1

    unsupported_payload = {
        "event_id": "unsupported-currency-sale",
        "type": "sale",
        "campaign_id": campaign_id,
        "customer_id": "unsupported-currency-customer",
        "amount": 10.005,
        "currency": "XYZ",
        "payment_sequence": 1,
        "good_date": str(date.today()),
        "payment_record_id": "unsupported-currency-payment",
    }
    invalid_currency_payload = {
        **unsupported_payload,
        "event_id": "invalid-currency-sale",
        "currency": "US1",
    }
    try:
        invalid_currency = await client.post(
            "/api/v1/events",
            headers={"X-API-Key": "test-api-key"},
            json=invalid_currency_payload,
        )
    except ValueError as exc:
        pytest.fail(f"invalid currency syntax should return HTTP 422: {exc}")
    assert invalid_currency.status_code == 422

    try:
        unsupported = await client.post(
            "/api/v1/events",
            headers={"X-API-Key": "test-api-key"},
            json=unsupported_payload,
        )
    except ValueError as exc:
        pytest.fail(f"unsupported currency should be held instead of raising: {exc}")
    assert unsupported.status_code == 200
    assert unsupported.json()["currency"] == "XYZ"
    assert unsupported.json()["amount"] == 10.01
    assert unsupported.json()["commission_status"] == "currency_unsupported"

    event_uuid = uuid.UUID(unsupported.json()["id"])
    async with async_session() as db:
        commission_count = await db.scalar(
            select(func.count(Commission.id)).where(Commission.event_id == event_uuid)
        )
    assert commission_count == 0

    monkeypatch.setitem(money.SUPPORTED_CURRENCY_EXPONENTS, "XYZ", 2)
    replay = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json=unsupported_payload,
    )
    assert replay.status_code == 200
    assert replay.json()["commission_status"] is None

    async with async_session() as db:
        commission_count = await db.scalar(
            select(func.count(Commission.id)).where(Commission.event_id == event_uuid)
        )
    assert commission_count == 1


@pytest.mark.asyncio
async def test_event_idempotency_is_scoped_to_tenant(
    client: AsyncClient, tenant: Tenant
):
    tenant_b_api_key = "tenant-b-event-key"
    event_id = "cross-tenant-idempotency-event"

    async with async_session() as db:
        tenant_b = Tenant(
            name="second-merchant",
            api_key_hash=hash_api_key(tenant_b_api_key),
        )
        account_a = AffiliateAccount(
            email="event-tenant-a@example.com",
            password_hash="unused",
            name="Tenant A Affiliate",
            country="US",
        )
        account_b = AffiliateAccount(
            email="event-tenant-b@example.com",
            password_hash="unused",
            name="Tenant B Affiliate",
            country="US",
        )
        db.add_all([tenant_b, account_a, account_b])
        await db.flush()

        affiliate_a = Affiliate(
            affiliate_account_id=account_a.id,
            tenant_id=tenant.id,
        )
        affiliate_b = Affiliate(
            affiliate_account_id=account_b.id,
            tenant_id=tenant_b.id,
        )
        db.add_all([affiliate_a, affiliate_b])
        await db.flush()

        campaign_a = Campaign(
            affiliate_id=affiliate_a.id,
            tenant_id=tenant.id,
            tracking_code="event-tenant-a-code",
            landing_url="https://example.com/a",
        )
        campaign_b = Campaign(
            affiliate_id=affiliate_b.id,
            tenant_id=tenant_b.id,
            tracking_code="event-tenant-b-code",
            landing_url="https://example.com/b",
        )
        db.add_all([campaign_a, campaign_b])
        await db.commit()
        tenant_b_id = str(tenant_b.id)

    event_a = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": event_id,
            "type": "click",
            "tracking_code": "event-tenant-a-code",
            "customer_id": "tenant-a-private-customer",
        },
    )
    event_b = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": tenant_b_api_key},
        json={
            "event_id": event_id,
            "type": "click",
            "tracking_code": "event-tenant-b-code",
            "customer_id": "tenant-b-customer",
        },
    )

    assert event_a.status_code == 200
    assert event_b.status_code == 200
    assert event_b.json()["tenant_id"] == tenant_b_id
    assert event_b.json()["id"] != event_a.json()["id"]
    assert event_b.json()["customer_id"] == "tenant-b-customer"

    async with async_session() as db:
        count = await db.scalar(
            select(func.count(Event.id)).where(Event.event_id == event_id)
        )
    assert count == 2


@pytest.mark.asyncio
async def test_tenant_webhook_is_retired(client: AsyncClient, tenant: Tenant):
    """Incoming payment-record ingestion was replaced by confirmed sale
    events carrying their own ``good_date`` and ``payment_record_id``."""
    response = await client.post(
        "/api/v1/webhooks/tenant",
        headers={"X-API-Key": "test-api-key"},
        json={
            "payment_record_id": "retired-pay-1",
            "customer_id": "cust-1",
            "amount": 100.0,
            "currency": "USD",
            "sequence_number": 1,
            "status": "paid",
        },
    )
    assert response.status_code == 410
    assert response.json()["detail"] == (
        "Incoming payment-record webhooks are retired; send a confirmed sale event"
    )


@pytest.mark.asyncio
async def test_sale_event_stores_payment_record_id_and_matures_on_good_date(
    client: AsyncClient, tenant: Tenant
):
    """``payment_record_id`` stays on the sale Event verbatim as the
    merchant's external correlation string (no FK to a payment row), and
    ``good_date`` alone — no incoming-payment webhook — controls when the
    commission becomes available."""
    async with async_session() as db:
        account = AffiliateAccount(
            email="sale-correlation@example.com",
            password_hash="unused",
            name="Sale Correlation Affiliate",
            country="US",
        )
        db.add(account)
        await db.flush()
        affiliate = Affiliate(
            affiliate_account_id=account.id, tenant_id=tenant.id
        )
        db.add(affiliate)
        await db.flush()
        contract = Contract(affiliate_id=affiliate.id)
        db.add(contract)
        await db.flush()
        db.add(
            Term(
                contract_id=contract.id,
                payment_sequence=1,
                commission_percent=10,
            )
        )
        db.add(
            Campaign(
                affiliate_id=affiliate.id,
                tenant_id=tenant.id,
                tracking_code="sale-correlation-code",
                landing_url="https://example.com/sale",
            )
        )
        await db.commit()

    good_date = date.today() - timedelta(days=5)
    sale = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "sale-correlation-1",
            "type": "sale",
            "tracking_code": "sale-correlation-code",
            "customer_id": "cust-correlation-1",
            "amount": 50.0,
            "currency": "USD",
            "payment_sequence": 1,
            "good_date": str(good_date),
            "payment_record_id": "merchant-tx-abc-123",
        },
    )
    assert sale.status_code == 200
    assert sale.json()["payment_record_id"] == "merchant-tx-abc-123"
    event_uuid = uuid.UUID(sale.json()["id"])

    async with async_session() as db:
        stored = await db.get(Event, event_uuid)
        assert stored.payment_record_id == "merchant-tx-abc-123"
        commission = (
            await db.execute(
                select(Commission).where(Commission.event_id == event_uuid)
            )
        ).scalar_one()
        assert commission.status == "pending"
        assert commission.available_on == good_date

    # No webhook call: maturing due commissions promotes purely on good_date.
    async with async_session() as db:
        assert await mature_due_commissions(db) == 1
    async with async_session() as db:
        assert (
            await db.scalar(
                select(Commission.status).where(Commission.event_id == event_uuid)
            )
            == "available"
        )


def test_sale_event_requires_good_date():
    with pytest.raises(ValidationError, match="good_date is required for sale events"):
        EventCreate(event_id="sale-without-date", type="sale", payment_record_id="pay-1")


@pytest.mark.parametrize("payment_record_id", [None, "", "   "])
def test_sale_event_requires_payment_record_id(payment_record_id):
    with pytest.raises(ValidationError, match="payment_record_id is required for sale events"):
        EventCreate(
            event_id="sale-without-payment-id",
            type="sale",
            good_date=date(2026, 10, 1),
            payment_record_id=payment_record_id,
        )


@pytest.mark.parametrize("event_type", ["click", "lead"])
def test_non_sale_event_does_not_require_good_date(event_type):
    event = EventCreate(event_id=f"{event_type}-without-date", type=event_type)
    assert event.good_date is None
