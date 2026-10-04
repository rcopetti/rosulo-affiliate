import asyncio
import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.db.models import AffiliateInvite, Payout, PayoutPayment
from app.services.password_reset import CODE_TTL_MINUTES

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates" / "email"

_env = Environment(
    loader=FileSystemLoader(_TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_email(name: str, **context) -> tuple[str, str]:
    """Render the plain-text and HTML bodies for the named email template."""
    context.setdefault("year", datetime.now(timezone.utc).year)
    text = _env.get_template(f"{name}.txt").render(**context)
    html = _env.get_template(f"{name}.html").render(**context)
    return text, html


def _build_invite_link(invite: AffiliateInvite) -> str:
    base = settings.frontend_url.rstrip("/")
    return f"{base}/register?token={invite.token}&email={invite.email}"


def _send_ses_email(to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
    # Provider retries stay disabled so a stalled or rejected send surfaces as
    # a delivery failure the application records and operators can retry,
    # rather than being hidden inside botocore's retry loop.
    client = boto3.client(
        "ses",
        region_name=settings.ses_region,
        config=Config(
            connect_timeout=5,
            read_timeout=15,
            retries={"total_max_attempts": 1},
        ),
    )
    message = {
        "Subject": {"Data": subject},
        "Body": {"Text": {"Data": body_text}},
    }
    if body_html:
        message["Body"]["Html"] = {"Data": body_html}
    client.send_email(
        Source=settings.email_from,
        Destination={"ToAddresses": [to]},
        Message=message,
    )


def _send_console_email(to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
    logger.info("[EMAIL] To: %s | Subject: %s\n%s", to, subject, body_text)


def _send_email_sync(to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
    if not settings.email_from:
        raise RuntimeError("email_from is not configured")

    if settings.email_backend == "ses":
        try:
            _send_ses_email(to, subject, body_text, body_html)
        except ClientError as exc:
            logger.exception("SES send failed: %s", exc)
            raise
    else:
        _send_console_email(to, subject, body_text, body_html)


async def send_email(to: str, subject: str, body_text: str, body_html: str | None = None) -> None:
    await asyncio.to_thread(_send_email_sync, to, subject, body_text, body_html)


async def send_invite_email(invite: AffiliateInvite, tenant_name: str) -> None:
    if not settings.email_from:
        logger.warning("email_from is not configured; skipping invite email to %s", invite.email)
        return
    expires_at = (
        invite.expires_at.strftime("%B %d, %Y at %H:%M UTC") if invite.expires_at else "N/A"
    )
    body_text, body_html = render_email(
        "invite",
        tenant_name=tenant_name,
        invite_url=_build_invite_link(invite),
        expires_at=expires_at,
    )
    subject = f"You've been invited to join {tenant_name} on Rosulo Affiliate"
    await send_email(invite.email, subject, body_text, body_html)


def build_payout_url(payout_id: uuid.UUID, tenant_id: uuid.UUID) -> str:
    """Deep link to the authenticated affiliate payout detail page.

    The payout UUID and tenant id are routing context only — the API remains
    the authorization boundary, so no token or secret ever goes in the URL.
    """
    base = settings.frontend_url.rstrip("/")
    return f"{base}/affiliate/payouts/{payout_id}?tenant_id={tenant_id}"


async def send_payout_paid_email(
    *,
    to: str,
    affiliate_name: str,
    payout: Payout,
    payment: PayoutPayment,
) -> None:
    """Notify the affiliate that their payout was paid via PayPal.

    Unlike invite/reset emails this intentionally has no ``email_from``
    short-circuit: an unconfigured sender must raise so the caller records
    the notification as ``failed`` (visible + retryable) instead of silently
    dropping the email.
    """
    amount_display = f"{Decimal(payment.amount):.2f} {payment.currency}"
    body_text, body_html = render_email(
        "payout_paid",
        affiliate_name=affiliate_name,
        amount_display=amount_display,
        transfer_reference=payment.transfer_reference,
        payout_url=build_payout_url(payout.id, payout.tenant_id),
    )
    subject = f"Your payout of {amount_display} has been sent"
    await send_email(to, subject, body_text, body_html)


async def send_password_reset_code(to: str, code: str) -> None:
    if not settings.email_from:
        logger.warning("email_from is not configured; skipping password reset email to %s", to)
        return
    body_text, body_html = render_email(
        "password_reset", code=code, expires_minutes=CODE_TTL_MINUTES
    )
    subject = "Your Rosulo Affiliate password reset code"
    await send_email(to, subject, body_text, body_html)
