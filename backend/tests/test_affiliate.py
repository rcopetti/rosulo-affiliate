from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_admin_create_invite(client: AsyncClient, tenant_user):
    admin_login = await client.post(
        "/api/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    r = await client.post(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "new@example.com"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "new@example.com"
    assert data["status"] == "pending"
    assert "token" in data


@pytest.mark.asyncio
async def test_admin_create_invite_sends_email(
    client: AsyncClient, tenant_user, monkeypatch
):
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr(settings, "email_from", "test@rosulo.dev")
    monkeypatch.setattr(settings, "frontend_url", "http://localhost:5173")
    send_mock = MagicMock()
    monkeypatch.setattr("app.services.email._send_console_email", send_mock)

    admin_login = await client.post(
        "/api/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    r = await client.post(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "with-email@example.com"},
    )
    assert r.status_code == 200
    send_mock.assert_called_once()
    args = send_mock.call_args[0]
    assert args[0] == "with-email@example.com"
    assert "Rosulo Affiliate" in args[1]


@pytest.mark.asyncio
async def test_admin_list_affiliates_after_accept(
    client: AsyncClient, tenant_user, tenant
):
    admin_login = await client.post(
        "/api/v1/auth/tenant/login",
        json={"email": "admin@allbum.me", "password": "admin123"},
    )
    admin_token = admin_login.json()["token"]

    invite = await client.post(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"email": "list@example.com"},
    )
    invite_token = invite.json()["token"]

    await client.post(
        "/api/v1/auth/affiliate/accept-invite",
        json={
            "token": invite_token,
            "email": "list@example.com",
            "password": "secret123",
            "name": "List Affiliate",
            "country": "US",
        },
    )

    r = await client.get(
        "/api/v1/admin/affiliates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert any(a["tenant_id"] == str(tenant.id) for a in data)
