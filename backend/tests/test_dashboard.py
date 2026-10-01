from datetime import date

import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_dashboards(client: AsyncClient, tenant: Tenant, tenant_user):
    admin_login = await client.post(
        "/api/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "dash@example.com"},
    )
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/api/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "dash@example.com",
            "password": "secret123",
            "name": "Dash Tester",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    token = accept.json()["token"]

    camp = await client.post(
        "/api/v1/affiliate/campaigns",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
        json={"name": "Dash Camp", "landing_url": "https://allbum.me/d"},
    )
    campaign_id = camp.json()["id"]

    empty_balance = await client.get(
        "/api/v1/affiliate/balance",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
    )
    assert empty_balance.status_code == 200
    assert empty_balance.json()["balances_by_currency"] == []
    assert empty_balance.json()["currency"] == "USD"
    assert empty_balance.json()["earned"] == 0

    await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "dash-click-1",
            "type": "click",
            "campaign_id": campaign_id,
            "customer_id": "cust-1",
            "referer": "https://x.com",
            "page_url": "https://allbum.me/d",
        },
    )

    for event_id, currency in (("dash-sale-usd", "USD"), ("dash-sale-eur", "EUR")):
        response = await client.post(
            "/api/v1/events",
            headers={"X-API-Key": "test-api-key"},
            json={
                "event_id": event_id,
                "type": "sale",
                "campaign_id": campaign_id,
                "customer_id": f"customer-{currency.lower()}",
                "amount": 100.0,
                "currency": currency,
                "payment_sequence": 1,
                "good_date": str(date.today()),
            },
        )
        assert response.status_code == 200

    affiliate_balance = await client.get(
        "/api/v1/affiliate/balance",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
    )
    assert affiliate_balance.status_code == 200
    assert {
        row["currency"] for row in affiliate_balance.json()["balances_by_currency"]
    } == {"USD", "EUR"}
    assert affiliate_balance.json()["earned"] is None
    assert affiliate_balance.json()["reversed"] is None
    assert affiliate_balance.json()["currency"] is None

    a_dash = await client.get(
        "/api/v1/affiliate/dashboard",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
    )
    assert a_dash.status_code == 200
    assert "balance" in a_dash.json()
    balance = a_dash.json()["balance"]
    assert {row["currency"] for row in balance["balances_by_currency"]} == {"USD", "EUR"}
    assert balance["earned"] is None
    assert balance["reversed"] is None
    assert balance["currency"] is None
    assert {row["currency"] for row in a_dash.json()["sales_by_sequence"]} == {"USD", "EUR"}

    t_dash = await client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert t_dash.status_code == 200
    assert "campaign_performance" in t_dash.json()
    assert {
        row["currency"] for row in t_dash.json()["commission_liability"]
    } == {"USD", "EUR"}
