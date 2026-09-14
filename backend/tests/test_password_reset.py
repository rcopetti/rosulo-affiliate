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
