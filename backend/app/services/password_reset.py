import secrets
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.db.models import AffiliateAccount, PasswordResetCode, TenantUser, now_utc

CODE_TTL_MINUTES = 5
VERIFIED_TTL_MINUTES = 10
MAX_ATTEMPTS = 3
LOCKOUT_MINUTES = 5


async def _get_row(db: AsyncSession, email: str, user_type: str) -> PasswordResetCode | None:
    result = await db.execute(
        select(PasswordResetCode).where(
            PasswordResetCode.email == email,
            PasswordResetCode.user_type == user_type,
        )
    )
    return result.scalar_one_or_none()


async def _account_exists(db: AsyncSession, email: str, user_type: str) -> bool:
    model = AffiliateAccount if user_type == "affiliate" else TenantUser
    result = await db.execute(select(model.id).where(model.email == email))
    return result.scalar_one_or_none() is not None


async def request_code(db: AsyncSession, email: str, user_type: str) -> str | None:
    """Create or replace the reset row. Returns the plaintext code to email,
    or None when nothing should be sent (locked, or unknown email — the row is
    still created so verify behaves identically for unregistered emails)."""
    now = now_utc()
    row = await _get_row(db, email, user_type)
    if row and row.locked_until and row.locked_until > now:
        return None
    code = f"{secrets.randbelow(1_000_000):06d}"
    if row is None:
        row = PasswordResetCode(email=email, user_type=user_type)
        db.add(row)
    row.code_hash = hash_password(code)
    row.attempts = 0
    row.expires_at = now + timedelta(minutes=CODE_TTL_MINUTES)
    row.reset_token_hash = None
    await db.commit()
    if not await _account_exists(db, email, user_type):
        return None
    return code


async def verify_code(db: AsyncSession, email: str, user_type: str, code: str) -> str:
    now = now_utc()
    row = await _get_row(db, email, user_type)
    if row and row.locked_until and row.locked_until > now:
        raise ValueError("locked")
    if row is None or row.expires_at < now or not row.code_hash:
        raise ValueError("invalid_or_expired_code")
    if not verify_password(code, row.code_hash):
        row.attempts += 1
        if row.attempts >= MAX_ATTEMPTS:
            row.code_hash = None
            row.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
            await db.commit()
            raise ValueError("locked")
        await db.commit()
        raise ValueError("invalid_or_expired_code")
    token = secrets.token_urlsafe(32)
    row.reset_token_hash = hash_password(token)
    row.expires_at = now + timedelta(minutes=VERIFIED_TTL_MINUTES)
    await db.commit()
    return token


async def confirm_reset(
    db: AsyncSession, email: str, user_type: str, reset_token: str, new_password: str
) -> None:
    now = now_utc()
    row = await _get_row(db, email, user_type)
    if (
        row is None
        or not row.reset_token_hash
        or row.expires_at < now
        or not verify_password(reset_token, row.reset_token_hash)
    ):
        raise ValueError("invalid_or_expired_token")
    model = AffiliateAccount if user_type == "affiliate" else TenantUser
    result = await db.execute(select(model).where(model.email == email))
    accounts = result.scalars().all()
    if not accounts:
        raise ValueError("invalid_or_expired_token")
    for account in accounts:
        account.password_hash = hash_password(new_password)
    await db.delete(row)
    await db.commit()
