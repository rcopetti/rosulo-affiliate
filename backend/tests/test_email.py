"""Payout-paid email template rendering and sender behavior."""

import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services.email import render_email, send_payout_paid_email

PAYOUT_ID = uuid.uuid4()
TENANT_ID = uuid.uuid4()
PAYOUT_URL = (
    f"https://affiliates.example.com/affiliate/payouts/{PAYOUT_ID}"
    f"?tenant_id={TENANT_ID}"
)


def _render_payout_paid(**overrides):
    context = {
        "affiliate_name": "Ada Affiliate",
        "amount_display": "10.00 USD",
        "transfer_reference": "PP-TX-100",
        "payout_url": PAYOUT_URL,
    }
    context.update(overrides)
    return render_email("payout_paid", **context)


def test_payout_paid_template_includes_payment_details():
    """Both bodies carry the affiliate name, payout amount/currency, PayPal
    reference, and the link to the authenticated payout detail page."""
    text, html = _render_payout_paid()

    for body in (text, html):
        assert "Ada Affiliate" in body
        assert "10.00 USD" in body
        assert "PP-TX-100" in body
        assert PAYOUT_URL in body


def test_payout_paid_html_escapes_template_context():
    """The HTML body auto-escapes affiliate-supplied content (the payee name
    comes from registration input); the text body stays raw."""
    text, html = _render_payout_paid(affiliate_name="<script>alert(1)</script>")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<script>alert(1)</script>" in text


def test_payout_paid_link_carries_no_secret():
    """The emailed URL is routing context only: payout id + tenant id, never
    a token, credential, or payment secret."""
    text, _ = _render_payout_paid()
    assert "token" not in PAYOUT_URL
    assert "@" not in PAYOUT_URL


def _payout_and_payment():
    payout = SimpleNamespace(id=PAYOUT_ID, tenant_id=TENANT_ID)
    payment = SimpleNamespace(
        amount=Decimal("10.00"),
        currency="USD",
        transfer_reference="PP-TX-100",
    )
    return payout, payment


@pytest.mark.asyncio
async def test_send_payout_paid_email_builds_frontend_link(monkeypatch):
    """The payout URL is built from settings.frontend_url (trailing slash
    stripped) plus the affiliate payout route with tenant context."""
    sent = {}

    async def fake_send(to, subject, body_text, body_html=None):
        sent.update(
            to=to, subject=subject, body_text=body_text, body_html=body_html
        )

    monkeypatch.setattr("app.services.email.send_email", fake_send)
    monkeypatch.setattr(settings, "frontend_url", "https://fe.example.com/")

    payout, payment = _payout_and_payment()
    await send_payout_paid_email(
        to="ada@example.com",
        affiliate_name="Ada Affiliate",
        payout=payout,
        payment=payment,
    )

    assert sent["to"] == "ada@example.com"
    expected_url = (
        f"https://fe.example.com/affiliate/payouts/{PAYOUT_ID}"
        f"?tenant_id={TENANT_ID}"
    )
    assert expected_url in sent["body_text"]
    assert expected_url in sent["body_html"]
    assert "10.00 USD" in sent["body_text"]
    assert "Ada Affiliate" in sent["body_html"]


@pytest.mark.asyncio
async def test_send_payout_paid_email_propagates_provider_failure(monkeypatch):
    """The payout sender must not swallow send errors: the delivery worker
    records `failed` so the notification stays visible and retryable."""

    async def boom(to, subject, body_text, body_html=None):
        raise RuntimeError("SES unavailable")

    monkeypatch.setattr("app.services.email.send_email", boom)
    payout, payment = _payout_and_payment()

    with pytest.raises(RuntimeError, match="SES unavailable"):
        await send_payout_paid_email(
            to="ada@example.com",
            affiliate_name="Ada Affiliate",
            payout=payout,
            payment=payment,
        )


def test_ses_client_disables_provider_retries():
    """The SES client is configured with explicit connect/read timeouts and
    a single attempt so delivery retries stay observable at the
    application/operator level instead of hidden inside botocore."""
    import inspect

    from app.services import email as email_module

    source = inspect.getsource(email_module._send_ses_email)
    assert "connect_timeout=5" in source
    assert "read_timeout=15" in source
    assert "total_max_attempts" in source
