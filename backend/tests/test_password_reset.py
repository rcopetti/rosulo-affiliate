import re
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.config import settings
from app.db.models import PasswordResetCode, now_utc
from app.db.session import async_session

BASE = "/api/v1/auth/password-reset"


def _capture_emails(monkeypatch) -> list[dict]:
    """Patch console email backend; returns a list of sent emails."""
    sent: list[dict] = []
    monkeypatch.setattr(settings, "email_backend", "console")
    monkeypatch.setattr(settings, "email_from", "test@rosulo.dev")

    def fake(to, subject, body_text, body_html=None):
        sent.append({"to": to, "subject": subject, "body": body_text})

    monkeypatch.setattr("app.services.email._send_console_email", fake)
    return sent


def _last_code(sent: list[dict]) -> str:
    match = re.search(r"\b(\d{6})\b", sent[-1]["body"])
    assert match, f"no 6-digit code in email body: {sent[-1]['body']}"
    return match.group(1)


def _wrong_code(real: str) -> str:
    return "000000" if real != "000000" else "000001"


async def _register_affiliate(client: AsyncClient, email: str, password: str = "oldpass123"):
    r = await client.post(
        "/api/v1/auth/affiliate/register",
        json={"email": email, "password": password, "name": "Reset Affiliate", "country": "US"},
    )
    assert r.status_code == 200, r.text


async def _request(client: AsyncClient, email: str, user_type: str = "affiliate"):
    r = await client.post(f"{BASE}/request", json={"email": email, "user_type": user_type})
    assert r.status_code == 200, r.text


async def _verify(client: AsyncClient, email: str, code: str, user_type: str = "affiliate"):
    return await client.post(
        f"{BASE}/verify", json={"email": email, "user_type": user_type, "code": code}
    )


@pytest.mark.asyncio
async def test_request_sends_code_for_known_affiliate(client: AsyncClient, monkeypatch):
    sent = _capture_emails(monkeypatch)
    await _register_affiliate(client, "req-aff@example.com")
    await _request(client, "req-aff@example.com")
    assert len(sent) == 1
    assert sent[0]["to"] == "req-aff@example.com"
    assert re.search(r"\b\d{6}\b", sent[0]["body"])


@pytest.mark.asyncio
async def test_request_unknown_email_is_silent(client: AsyncClient, monkeypatch):
    sent = _capture_emails(monkeypatch)
    await _request(client, "ghost@example.com")
    assert sent == []


@pytest.mark.asyncio
async def test_verify_correct_code_returns_reset_token(client: AsyncClient, monkeypatch):
    sent = _capture_emails(monkeypatch)
    await _register_affiliate(client, "verify-aff@example.com")
    await _request(client, "verify-aff@example.com")
    code = _last_code(sent)
    v = await _verify(client, "verify-aff@example.com", code)
    assert v.status_code == 200
    assert v.json()["reset_token"]


@pytest.mark.asyncio
async def test_verify_wrong_code_is_generic_error(client: AsyncClient, monkeypatch):
    sent = _capture_emails(monkeypatch)
    await _register_affiliate(client, "wrong-aff@example.com")
    await _request(client, "wrong-aff@example.com")
    code = _last_code(sent)
    v = await _verify(client, "wrong-aff@example.com", _wrong_code(code))
    assert v.status_code == 400
    assert v.json()["detail"] == "invalid_or_expired_code"


@pytest.mark.asyncio
async def test_affiliate_reset_happy_path(client: AsyncClient, monkeypatch):
    sent = _capture_emails(monkeypatch)
    email = "happy-aff@example.com"
    await _register_affiliate(client, email)
    await _request(client, email)
    v = await _verify(client, email, _last_code(sent))
    token = v.json()["reset_token"]
    c = await client.post(
        f"{BASE}/confirm",
        json={"email": email, "user_type": "affiliate", "reset_token": token, "new_password": "newpass456"},
    )
    assert c.status_code == 200
    login = await client.post(
        "/api/v1/auth/affiliate/login", json={"email": email, "password": "newpass456"}
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_tenant_reset_happy_path(client: AsyncClient, monkeypatch):
    sent = _capture_emails(monkeypatch)
    email = "reset-admin@example.com"
    reg = await client.post(
        "/api/v1/auth/tenant/register",
        json={"tenant_name": "Reset Corp", "email": email, "password": "oldpass123"},
    )
    assert reg.status_code == 200, reg.text
    await _request(client, email, user_type="tenant")
    v = await _verify(client, email, _last_code(sent), user_type="tenant")
    token = v.json()["reset_token"]
    c = await client.post(
        f"{BASE}/confirm",
        json={"email": email, "user_type": "tenant", "reset_token": token, "new_password": "newpass456"},
    )
    assert c.status_code == 200
    login = await client.post(
        "/api/v1/auth/tenant/login", json={"email": email, "password": "newpass456"}
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_three_wrong_attempts_locks_and_blocks_resend(client: AsyncClient, monkeypatch):
    sent = _capture_emails(monkeypatch)
    email = "lock-aff@example.com"
    await _register_affiliate(client, email)
    await _request(client, email)
    real = _last_code(sent)
    wrong = _wrong_code(real)

    for _ in range(2):
        v = await _verify(client, email, wrong)
        assert v.status_code == 400
        assert v.json()["detail"] == "invalid_or_expired_code"

    v = await _verify(client, email, wrong)
    assert v.status_code == 400
    assert v.json()["detail"] == "locked"

    # Even the correct code is dead while locked
    v = await _verify(client, email, real)
    assert v.status_code == 400
    assert v.json()["detail"] == "locked"

    # Request while locked: 200 but no new email
    await _request(client, email)
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_request_works_after_lockout_expires(client: AsyncClient, monkeypatch):
    sent = _capture_emails(monkeypatch)
    email = "unlock-aff@example.com"
    await _register_affiliate(client, email)
    await _request(client, email)
    real = _last_code(sent)
    wrong = _wrong_code(real)
    for _ in range(3):
        await _verify(client, email, wrong)

    async with async_session() as db:
        await db.execute(
            update(PasswordResetCode)
            .where(PasswordResetCode.email == email, PasswordResetCode.user_type == "affiliate")
            .values(locked_until=now_utc() - timedelta(seconds=1))
        )
        await db.commit()

    await _request(client, email)
    assert len(sent) == 2
    v = await _verify(client, email, _last_code(sent))
    assert v.status_code == 200


@pytest.mark.asyncio
async def test_expired_code_is_rejected(client: AsyncClient, monkeypatch):
    sent = _capture_emails(monkeypatch)
    email = "expired-aff@example.com"
    await _register_affiliate(client, email)
    await _request(client, email)
    real = _last_code(sent)

    async with async_session() as db:
        await db.execute(
            update(PasswordResetCode)
            .where(PasswordResetCode.email == email, PasswordResetCode.user_type == "affiliate")
            .values(expires_at=now_utc() - timedelta(seconds=1))
        )
        await db.commit()

    v = await _verify(client, email, real)
    assert v.status_code == 400
    assert v.json()["detail"] == "invalid_or_expired_code"


@pytest.mark.asyncio
async def test_resend_invalidates_previous_code(client: AsyncClient, monkeypatch):
    sent = _capture_emails(monkeypatch)
    email = "resend-aff@example.com"
    await _register_affiliate(client, email)
    await _request(client, email)
    first = _last_code(sent)
    await _request(client, email)
    assert len(sent) == 2
    second = _last_code(sent)

    v = await _verify(client, email, first)
    if first != second:
        assert v.status_code == 400
    v = await _verify(client, email, second)
    assert v.status_code == 200


@pytest.mark.asyncio
async def test_confirm_with_bad_token_fails(client: AsyncClient, monkeypatch):
    sent = _capture_emails(monkeypatch)
    email = "badtok-aff@example.com"
    await _register_affiliate(client, email)
    await _request(client, email)
    await _verify(client, email, _last_code(sent))
    c = await client.post(
        f"{BASE}/confirm",
        json={"email": email, "user_type": "affiliate", "reset_token": "bogus-token", "new_password": "newpass456"},
    )
    assert c.status_code == 400
    assert c.json()["detail"] == "invalid_or_expired_token"
