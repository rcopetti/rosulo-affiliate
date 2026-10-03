from datetime import date, timedelta

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
                "payment_record_id": f"pay-{event_id}",
            },
        )
        assert response.status_code == 200

    affiliate_balance = await client.get(
        "/api/v1/affiliate/balance",
        headers={"Authorization": f"Bearer {token}", "X-Tenant-Id": str(tenant.id)},
    )
    assert affiliate_balance.status_code == 200
    balances_by_currency = {
        row["currency"]: row for row in affiliate_balance.json()["balances_by_currency"]
    }
    assert set(balances_by_currency) == {"USD", "EUR"}
    assert balances_by_currency["USD"]["earned"] == 10.0
    assert balances_by_currency["EUR"]["earned"] == 10.0
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
    sales_by_currency = {
        row["currency"]: row for row in a_dash.json()["sales_by_sequence"]
    }
    assert set(sales_by_currency) == {"USD", "EUR"}
    assert sales_by_currency["USD"]["amount"] == 10.0
    assert sales_by_currency["EUR"]["amount"] == 10.0

    sales_volume = a_dash.json()["sales_volume"]
    assert len(sales_volume) == 1
    assert sales_volume[0]["count"] == 2

    t_dash = await client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert t_dash.status_code == 200
    assert "campaign_performance" in t_dash.json()
    liability_by_currency = {
        row["currency"]: row for row in t_dash.json()["commission_liability"]
    }
    assert set(liability_by_currency) == {"USD", "EUR"}
    assert liability_by_currency["USD"]["gross"] == 10.0
    assert liability_by_currency["EUR"]["gross"] == 10.0


@pytest.mark.asyncio
async def test_reserved_commissions_remain_in_tenant_liability(
    client: AsyncClient, payout_scenario
):
    due = date.today() - timedelta(days=1)
    selected = await payout_scenario.create_commission(
        due, "liab-selected-1", status="available"
    )
    await payout_scenario.create_commission(
        due, "liab-available-1", status="available"
    )
    await payout_scenario.create_commission(
        due, "liab-pending-1", status="pending"
    )

    reserve = await client.post(
        "/api/v1/affiliate/payout-requests",
        headers=payout_scenario.affiliate_headers,
        json={"currency": "USD", "commission_ids": [str(selected)]},
    )
    assert reserve.status_code == 200
    assert await payout_scenario.commission_status(selected) == "reserved"

    response = await client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {payout_scenario.admin_token}"},
    )
    assert response.status_code == 200
    usd = next(
        row
        for row in response.json()["commission_liability"]
        if row["currency"] == "USD"
    )
    # available + pending + reserved commissions all remain merchant liability
    assert usd["gross"] == 30.0
