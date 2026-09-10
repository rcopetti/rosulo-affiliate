import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Affiliate, Tenant


@pytest.mark.asyncio
async def test_admin_get_contract(client: AsyncClient, tenant: Tenant):
    reg = await client.post(
        "/v1/admin/affiliates/register",
        headers={"X-API-Key": "test-api-key"},
        json={
            "email": "contract@example.com",
            "password": "secret123",
            "name": "Contract Test",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    affiliate_id = reg.json()["id"]
    r = await client.get(
        f"/v1/admin/affiliates/{affiliate_id}/contract",
        headers={"X-API-Key": "test-api-key"},
    )
    assert r.status_code == 200
    assert r.json()["active"] is True
