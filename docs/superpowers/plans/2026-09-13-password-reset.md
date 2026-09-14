# Password Reset via 6-Digit Email Code — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let tenant users and affiliate accounts reset a forgotten password via a 6-digit code emailed to them, with 3 attempts per code and a 5-minute freeze after exhaustion.

**Architecture:** New `password_reset_codes` table (one row per `(email, user_type)`), a `password_reset` service with `request_code`/`verify_code`/`confirm_reset`, and three endpoints under `/api/v1/auth/password-reset/`. All responses are silent/generic to prevent email enumeration — including "phantom" rows for unknown emails. Frontend gets a shared `ForgotPasswordPage` mounted at `/forgot-password` and `/admin/forgot-password`.

**Tech Stack:** FastAPI + async SQLAlchemy + Postgres + Alembic + pytest/httpx (backend); React + react-router + axios + vitest/testing-library (frontend).

**Spec:** `docs/superpowers/specs/2026-09-13-password-reset-design.md`

**Working dir notes:**
- Backend commands run from `backend/` (uses `uv`: `uv run pytest`, `uv run alembic`).
- Tests require the dev Postgres (`docker-compose up -d` in `backend/` if not running); conftest creates a `_test` database automatically.
- Frontend commands run from `frontend/` (`npm run test`, `npm run build`).

---

### Task 1: `PasswordResetCode` model + Alembic migration

**Files:**
- Modify: `backend/app/db/models.py` (append at end)
- Create: `backend/alembic/versions/f7a8b9c0d123_add_password_reset_codes.py`

- [ ] **Step 1: Add the model**

Append to `backend/app/db/models.py`:

```python
class PasswordResetCode(Base):
    __tablename__ = "password_reset_codes"
    __table_args__ = (UniqueConstraint("email", "user_type"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, nullable=False, index=True)
    user_type = Column(String, nullable=False)
    code_hash = Column(String, nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    reset_token_hash = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=now_utc)
```

`UniqueConstraint`, `Integer`, `DateTime`, `UUID`, `uuid`, and `now_utc` are already imported in this file.

- [ ] **Step 2: Create the migration**

Current head is `c1d2e3f4a567`. Create `backend/alembic/versions/f7a8b9c0d123_add_password_reset_codes.py`:

```python
"""add password reset codes

Revision ID: f7a8b9c0d123
Revises: c1d2e3f4a567
Create Date: 2026-09-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7a8b9c0d123'
down_revision: Union[str, None] = 'c1d2e3f4a567'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'password_reset_codes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('user_type', sa.String(), nullable=False),
        sa.Column('code_hash', sa.String(), nullable=True),
        sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reset_token_hash', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email', 'user_type'),
    )
    op.create_index(op.f('ix_password_reset_codes_email'), 'password_reset_codes', ['email'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_password_reset_codes_email'), table_name='password_reset_codes')
    op.drop_table('password_reset_codes')
```

- [ ] **Step 3: Verify model imports and migration applies**

Run from `backend/`:
```bash
uv run python -c "from app.db.models import PasswordResetCode; print(PasswordResetCode.__table__.columns.keys())"
```
Expected: prints column list including `locked_until`, `reset_token_hash`.

```bash
uv run alembic upgrade head
```
Expected: `Running upgrade c1d2e3f4a567 -> f7a8b9c0d123, add password reset codes`

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/models.py backend/alembic/versions/f7a8b9c0d123_add_password_reset_codes.py
git commit -m "feat: add password_reset_codes table"
```

---

### Task 2: Schemas + email helper

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `backend/app/services/email.py` (append)

- [ ] **Step 1: Add request/response schemas**

In `backend/app/schemas/auth.py`, update the import and append:

```python
from typing import Literal

from pydantic import BaseModel, EmailStr, Field
```

```python
class PasswordResetRequest(BaseModel):
    email: EmailStr
    user_type: Literal["tenant", "affiliate"]


class PasswordResetVerify(PasswordResetRequest):
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class PasswordResetVerifyResponse(BaseModel):
    reset_token: str


class PasswordResetConfirm(PasswordResetRequest):
    reset_token: str
    new_password: str = Field(min_length=8)
```

- [ ] **Step 2: Add `send_password_reset_code`**

Append to `backend/app/services/email.py`:

```python
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
```

- [ ] **Step 3: Verify imports**

```bash
uv run python -c "from app.schemas.auth import PasswordResetConfirm; from app.services.email import send_password_reset_code; print('ok')"
```
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/auth.py backend/app/services/email.py
git commit -m "feat: password reset schemas and reset-code email"
```

---

### Task 3: `request` endpoint — write failing tests first

**Files:**
- Create: `backend/tests/test_password_reset.py`
- Create: `backend/app/services/password_reset.py`
- Create: `backend/app/api/v1/auth/password_reset.py`
- Modify: `backend/app/api/v1/__init__.py`

- [ ] **Step 1: Write the failing test file**

Create `backend/tests/test_password_reset.py`:

```python
import re
from datetime import timedelta
from unittest.mock import MagicMock

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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && uv run pytest tests/test_password_reset.py -v
```
Expected: FAIL — `404` on `/api/v1/auth/password-reset/request`.

- [ ] **Step 3: Implement the service**

Create `backend/app/services/password_reset.py`:

```python
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
```

- [ ] **Step 4: Implement the router and register it**

Create `backend/app/api/v1/auth/password_reset.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.dependencies import get_db
from app.schemas.auth import (
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetVerify,
    PasswordResetVerifyResponse,
)
from app.services import email as email_service
from app.services import password_reset as reset_service

router = APIRouter()


@router.post("/request")
async def request_reset(data: PasswordResetRequest, db: AsyncSession = Depends(get_db)):
    code = await reset_service.request_code(db, data.email, data.user_type)
    if code is not None:
        await email_service.send_password_reset_code(data.email, code)
    return {"status": "ok"}


@router.post("/verify", response_model=PasswordResetVerifyResponse)
async def verify_reset(data: PasswordResetVerify, db: AsyncSession = Depends(get_db)):
    try:
        token = await reset_service.verify_code(db, data.email, data.user_type, data.code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"reset_token": token}


@router.post("/confirm")
async def confirm_reset(data: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    try:
        await reset_service.confirm_reset(
            db, data.email, data.user_type, data.reset_token, data.new_password
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok"}
```

In `backend/app/api/v1/__init__.py`, add the import (with the other auth imports, after line 16):

```python
from app.api.v1.auth import password_reset as auth_password_reset
```

and register after the `auth_tenant` line (line 23):

```python
router.include_router(auth_password_reset.router, prefix="/auth/password-reset", tags=["auth"])
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd backend && uv run pytest tests/test_password_reset.py -v
```
Expected: 4 PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/password_reset.py backend/app/api/v1/auth/password_reset.py backend/app/api/v1/__init__.py backend/tests/test_password_reset.py
git commit -m "feat: password reset request/verify/confirm endpoints"
```

---

### Task 4: Confirm + full flow tests (happy paths, lockout, expiry, resend)

**Files:**
- Modify: `backend/tests/test_password_reset.py` (append tests)

- [ ] **Step 1: Append the remaining tests**

```python
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
    assert second != first or True  # codes could collide; verify behavior instead

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
```

- [ ] **Step 2: Run the full reset test file**

```bash
cd backend && uv run pytest tests/test_password_reset.py -v
```
Expected: 11 PASSED.

- [ ] **Step 3: Run the whole backend suite (regression)**

```bash
cd backend && uv run pytest -v
```
Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_password_reset.py
git commit -m "test: password reset flow, lockout, expiry, resend coverage"
```

---

### Task 5: Frontend API functions

**Files:**
- Modify: `frontend/src/api/auth.ts` (append)

- [ ] **Step 1: Add the API functions**

Append to `frontend/src/api/auth.ts`:

```typescript
export type ResetUserType = 'affiliate' | 'tenant';

export interface PasswordResetRequestInput {
  email: string;
  user_type: ResetUserType;
}

export interface PasswordResetVerifyInput extends PasswordResetRequestInput {
  code: string;
}

export interface PasswordResetConfirmInput extends PasswordResetRequestInput {
  reset_token: string;
  new_password: string;
}

export async function requestPasswordReset(data: PasswordResetRequestInput): Promise<void> {
  await api.post('/auth/password-reset/request', data);
}

export async function verifyPasswordResetCode(
  data: PasswordResetVerifyInput
): Promise<{ reset_token: string }> {
  const res = await api.post<{ reset_token: string }>('/auth/password-reset/verify', data);
  return res.data;
}

export async function confirmPasswordReset(data: PasswordResetConfirmInput): Promise<void> {
  await api.post('/auth/password-reset/confirm', data);
}
```

- [ ] **Step 2: Typecheck**

```bash
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/auth.ts
git commit -m "feat(ui): password reset api client functions"
```

---

### Task 6: `ForgotPasswordPage` + routes + login links

**Files:**
- Create: `frontend/src/pages/ForgotPasswordPage.tsx`
- Modify: `frontend/src/router.tsx`
- Modify: `frontend/src/pages/LoginPage.tsx:50-52`
- Modify: `frontend/src/pages/admin/LoginPage.tsx:50-52`

- [ ] **Step 1: Create the page component**

Create `frontend/src/pages/ForgotPasswordPage.tsx`:

```tsx
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { AxiosError } from 'axios';
import {
  confirmPasswordReset,
  requestPasswordReset,
  verifyPasswordResetCode,
  ResetUserType,
} from '@/api/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Card, CardHeader, CardTitle } from '@/components/ui/Card';

type Step = 'email' | 'code' | 'password' | 'done';

interface ForgotPasswordPageProps {
  userType: ResetUserType;
  loginPath: string;
  title: string;
}

export function ForgotPasswordPage({ userType, loginPath, title }: ForgotPasswordPageProps) {
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submitEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await requestPasswordReset({ email, user_type: userType });
      setNotice('If that email is registered, a 6-digit code is on its way.');
      setStep('code');
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    setLoading(true);
    setError(null);
    try {
      await requestPasswordReset({ email, user_type: userType });
      setCode('');
      setNotice('If that email is registered, a new code is on its way. Previous codes no longer work.');
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const submitCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await verifyPasswordResetCode({ email, user_type: userType, code });
      setResetToken(res.reset_token);
      setNotice(null);
      setStep('password');
    } catch (err) {
      const detail = (err as AxiosError<{ detail?: string }>).response?.data?.detail;
      setError(
        detail === 'locked'
          ? 'Too many attempts. Please wait 5 minutes and request a new code.'
          : 'Invalid or expired code. Check the code and try again.'
      );
    } finally {
      setLoading(false);
    }
  };

  const submitPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== passwordConfirm) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await confirmPasswordReset({
        email,
        user_type: userType,
        reset_token: resetToken,
        new_password: password,
      });
      setStep('done');
    } catch {
      setError('This reset has expired. Please request a new code.');
      setStep('email');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>{title}</CardTitle>
        </CardHeader>
        {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
        {notice && <p className="mb-4 text-sm text-slate-600">{notice}</p>}

        {step === 'email' && (
          <form onSubmit={submitEmail} className="space-y-4">
            <Input
              id="reset-email"
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <Button type="submit" isLoading={loading} className="w-full">
              Send reset code
            </Button>
          </form>
        )}

        {step === 'code' && (
          <form onSubmit={submitCode} className="space-y-4">
            <Input
              id="reset-code"
              label="6-digit code"
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
              required
            />
            <Button type="submit" isLoading={loading} className="w-full">
              Verify code
            </Button>
            <Button type="button" variant="secondary" onClick={resend} isLoading={loading} className="w-full">
              Resend code
            </Button>
          </form>
        )}

        {step === 'password' && (
          <form onSubmit={submitPassword} className="space-y-4">
            <Input
              id="reset-password"
              label="New password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <Input
              id="reset-password-confirm"
              label="Confirm new password"
              type="password"
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              required
            />
            <Button type="submit" isLoading={loading} className="w-full">
              Set new password
            </Button>
          </form>
        )}

        {step === 'done' && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">Your password has been updated. You can now log in.</p>
            <Link to={loginPath} className="text-brand-600 hover:underline">
              Back to login
            </Link>
          </div>
        )}

        {step !== 'done' && (
          <p className="mt-4 text-center text-sm text-slate-600">
            <Link to={loginPath} className="text-brand-600 hover:underline">
              Back to login
            </Link>
          </p>
        )}
      </Card>
    </div>
  );
}

export function AffiliateForgotPasswordPage() {
  return <ForgotPasswordPage userType="affiliate" loginPath="/login" title="Reset affiliate password" />;
}

export function AdminForgotPasswordPage() {
  return <ForgotPasswordPage userType="tenant" loginPath="/admin/login" title="Reset admin password" />;
}
```

Notes: `Button` supports `variant="secondary"` (already used in `RegisterPage.tsx`).
The `id` props on `Input` are required — `Input` only wires `label htmlFor` when `id`
or `name` is set (`inputId = id || props.name`); without them `getByLabelText` in
tests (and screen readers) won't associate the labels.

- [ ] **Step 2: Register the routes**

In `frontend/src/router.tsx`, add after the `register` route (line 37):

```tsx
      {
        path: 'forgot-password',
        lazy: async () => ({
          Component: (await import('@/pages/ForgotPasswordPage')).AffiliateForgotPasswordPage,
        }),
      },
```

and after the `admin/register` route (line 95):

```tsx
      {
        path: 'admin/forgot-password',
        lazy: async () => ({
          Component: (await import('@/pages/ForgotPasswordPage')).AdminForgotPasswordPage,
        }),
      },
```

- [ ] **Step 3: Add "Forgot password?" links**

In `frontend/src/pages/LoginPage.tsx`, inside the form after the register `<p>` (lines 50-52), add:

```tsx
          <p className="text-center text-sm text-slate-600">
            <Link to="/forgot-password" className="text-brand-600 hover:underline">
              Forgot password?
            </Link>
          </p>
```

In `frontend/src/pages/admin/LoginPage.tsx`, add a `Link` import from `react-router-dom` (extend the existing import on line 2) and inside the form after the `Button` (line 52), add:

```tsx
          <p className="text-center text-sm text-slate-600">
            <Link to="/admin/forgot-password" className="text-brand-600 hover:underline">
              Forgot password?
            </Link>
          </p>
```

- [ ] **Step 4: Typecheck + build**

```bash
cd frontend && npx tsc --noEmit && npm run build
```
Expected: clean build.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ForgotPasswordPage.tsx frontend/src/router.tsx frontend/src/pages/LoginPage.tsx frontend/src/pages/admin/LoginPage.tsx
git commit -m "feat(ui): forgot password pages for affiliate and admin"
```

---

### Task 7: Frontend component test

**Files:**
- Create: `frontend/src/tests/pages/ForgotPasswordPage.test.tsx`

- [ ] **Step 1: Write the test**

```tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AffiliateForgotPasswordPage } from '@/pages/ForgotPasswordPage';
import { requestPasswordReset, verifyPasswordResetCode, confirmPasswordReset } from '@/api/auth';

vi.mock('@/api/auth', () => ({
  requestPasswordReset: vi.fn().mockResolvedValue(undefined),
  verifyPasswordResetCode: vi.fn(),
  confirmPasswordReset: vi.fn().mockResolvedValue(undefined),
}));

const renderPage = () =>
  render(
    <MemoryRouter>
      <AffiliateForgotPasswordPage />
    </MemoryRouter>
  );

describe('AffiliateForgotPasswordPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('requests a code and advances to the code step', async () => {
    renderPage();
    await userEvent.type(screen.getByLabelText(/^email/i), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: /send reset code/i }));
    await waitFor(() =>
      expect(requestPasswordReset).toHaveBeenCalledWith({ email: 'a@b.com', user_type: 'affiliate' })
    );
    expect(await screen.findByLabelText(/^6-digit code/i)).toBeInTheDocument();
  });

  it('shows a generic error on a wrong code', async () => {
    vi.mocked(verifyPasswordResetCode).mockRejectedValue({
      response: { data: { detail: 'invalid_or_expired_code' } },
    });
    renderPage();
    await userEvent.type(screen.getByLabelText(/^email/i), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: /send reset code/i }));
    await userEvent.type(await screen.findByLabelText(/^6-digit code/i), '123456');
    await userEvent.click(screen.getByRole('button', { name: /verify code/i }));
    expect(await screen.findByText(/invalid or expired code/i)).toBeInTheDocument();
  });

  it('advances to password step and confirms reset', async () => {
    vi.mocked(verifyPasswordResetCode).mockResolvedValue({ reset_token: 'tok-1' });
    renderPage();
    await userEvent.type(screen.getByLabelText(/^email/i), 'a@b.com');
    await userEvent.click(screen.getByRole('button', { name: /send reset code/i }));
    await userEvent.type(await screen.findByLabelText(/^6-digit code/i), '123456');
    await userEvent.click(screen.getByRole('button', { name: /verify code/i }));
    await userEvent.type(await screen.findByLabelText(/^new password/i), 'newpass456');
    await userEvent.type(screen.getByLabelText(/^confirm new password/i), 'newpass456');
    await userEvent.click(screen.getByRole('button', { name: /set new password/i }));
    await waitFor(() =>
      expect(confirmPasswordReset).toHaveBeenCalledWith({
        email: 'a@b.com',
        user_type: 'affiliate',
        reset_token: 'tok-1',
        new_password: 'newpass456',
      })
    );
    expect(await screen.findByText(/password has been updated/i)).toBeInTheDocument();
  });
});
```

Note: label queries use start-anchored regexes — `required` inputs render a `*` inside
the `<label>`, so exact strings would fail. `/^new password/i` still won't match
"Confirm new password" because `^` anchors at the start.

- [ ] **Step 2: Run the test**

```bash
cd frontend && npm run test
```
Expected: all tests pass (new file + existing Button test).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/tests/pages/ForgotPasswordPage.test.tsx
git commit -m "test(ui): forgot password page step flow"
```

---

### Task 8: Final verification

- [ ] **Step 1: Backend suite**

```bash
cd backend && uv run pytest -v
```
Expected: all green.

- [ ] **Step 2: Frontend checks**

```bash
cd frontend && npx tsc --noEmit && npm run test && npm run build
```
Expected: clean.

- [ ] **Step 3: Manual smoke (optional, if dev servers run locally)**

Console email backend prints the code to backend logs when `email_from` is set. Exercise `/forgot-password` end-to-end against the local dev stack.
