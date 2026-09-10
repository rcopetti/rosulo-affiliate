import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    reg = await client.post(
        "/v1/auth/affiliate/register",
        json={
            "email": "aff@example.com",
            "password": "secret123",
            "name": "Test Affiliate",
            "country": "US",
            "tax_status": "us_person",
        },
    )
    assert reg.status_code == 200
    token = reg.json()["access_token"]

    login = await client.post(
        "/v1/auth/affiliate/login",
        json={"email": "aff@example.com", "password": "secret123"},
    )
    assert login.status_code == 200
    assert "access_token" in login.json()
