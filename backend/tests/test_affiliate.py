import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Tenant


@pytest.mark.asyncio
async def test_admin_create_affiliate(client: AsyncClient, tenant: Tenant):
    r = await client.post(
        "/v1/admin/affiliates/register",
        headers={"X-API-Key": "test-api-key"},
        json={
            "email": "new@example.com",
            "password": "secret123",
            "name": "New Affiliate",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["tenant_id"] == str(tenant.id)
