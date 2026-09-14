import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.db.models import AffiliateInvite
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
    client = boto3.client("ses", region_name=settings.ses_region)
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


async def send_password_reset_code(to: str, code: str) -> None:
    if not settings.email_from:
        logger.warning("email_from is not configured; skipping password reset email to %s", to)
        return
    body_text, body_html = render_email(
        "password_reset", code=code, expires_minutes=CODE_TTL_MINUTES
    )
    subject = "Your Rosulo Affiliate password reset code"
    await send_email(to, subject, body_text, body_html)
