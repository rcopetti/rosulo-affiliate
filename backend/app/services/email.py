import asyncio
import logging

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.db.models import AffiliateInvite

logger = logging.getLogger(__name__)


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
    link = _build_invite_link(invite)
    subject = f"You've been invited to join {tenant_name} on Rosulo Affiliate"
    body_text = (
        f"Hi,\n\n"
        f"You have been invited to join {tenant_name} as an affiliate on Rosulo Affiliate.\n\n"
        f"Accept your invitation:\n{link}\n\n"
        f"This link expires on {invite.expires_at.isoformat() if invite.expires_at else 'N/A'}.\n"
    )
    body_html = (
        f"<p>Hi,</p>"
        f"<p>You have been invited to join <strong>{tenant_name}</strong> as an affiliate on Rosulo Affiliate.</p>"
        f'<p><a href="{link}">Accept your invitation</a></p>'
        f"<p>This link expires on {invite.expires_at.isoformat() if invite.expires_at else 'N/A'}.</p>"
    )
    await send_email(invite.email, subject, body_text, body_html)


async def send_password_reset_code(to: str, code: str) -> None:
    if not settings.email_from:
        logger.warning("email_from is not configured; skipping password reset email to %s", to)
        return
    subject = "Your Rosulo Affiliate password reset code"
    body_text = (
        f"Hi,\n\n"
        f"Your password reset code is: {code}\n\n"
        f"It expires in 5 minutes. If you did not request a password reset, ignore this email.\n"
    )
    body_html = (
        f"<p>Hi,</p>"
        f"<p>Your password reset code is: <strong>{code}</strong></p>"
        f"<p>It expires in 5 minutes. If you did not request a password reset, ignore this email.</p>"
    )
    await send_email(to, subject, body_text, body_html)
