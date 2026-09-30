import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.security import hash_api_key
from app.db.models import Affiliate, AffiliateAccount, Campaign, Commission, Event, Tenant
from app.db.session import async_session


@pytest.mark.asyncio
async def test_event_ingestion(client: AsyncClient, tenant: Tenant, tenant_user):
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
