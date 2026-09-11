import pytest
from httpx import AsyncClient

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_admin_get_contract(client: AsyncClient, tenant: Tenant, tenant_user):
    admin_login = await client.post(
        "/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "contract@example.com"},
    )
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "contract@example.com",
            "password": "secret123",
            "name": "Contract Test",
            "country": "US",
            "tax_status": "us_person",
        },
    )

    affiliates = await client.get(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    account_id = accept.json()["account"]["id"]
    affiliate_id = next(a["id"] for a in affiliates.json() if a["account_id"] == account_id)

    r = await client.get(
        f"/v1/admin/affiliates/{affiliate_id}/contract",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["active"] is True


@pytest.mark.asyncio
async def test_update_contract_persists_terms(client: AsyncClient, tenant: Tenant, tenant_user):
    admin_login = await client.post(
        "/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "terms-save@example.com"},
    )
    invite_token = invite.json()["token"]

    accept = await client.post(
        "/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "terms-save@example.com",
            "password": "secret123",
            "name": "Terms Save",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    account_id = accept.json()["account"]["id"]

    affiliates = await client.get(
        "/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    affiliate_id = next(a["id"] for a in affiliates.json() if a["account_id"] == account_id)

    contract = (
        await client.get(
            f"/v1/admin/affiliates/{affiliate_id}/contract",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    ).json()
    existing_term = contract["terms"][0]

    # Update the existing term's commission and add a second term.
    payload = {
        "terms": [
            {
                "id": existing_term["id"],
                "payment_sequence": 1,
                "commission_percent": 15,
                "minimum_threshold": 50,
            },
            {
                "id": "new-term",
                "payment_sequence": 2,
                "commission_percent": 5,
            },
        ]
    }
    put = await client.put(
        f"/v1/admin/affiliates/{affiliate_id}/contract",
        headers={"Authorization": f"Bearer {admin_token}"},
        json=payload,
    )
    assert put.status_code == 200

    saved = (
        await client.get(
            f"/v1/admin/affiliates/{affiliate_id}/contract",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
    ).json()
    assert len(saved["terms"]) == 2
    updated = next(t for t in saved["terms"] if t["id"] == existing_term["id"])
    assert updated["commission_percent"] == 15
    assert updated["minimum_threshold"] == 50
    assert any(t["payment_sequence"] == 2 for t in saved["terms"])
