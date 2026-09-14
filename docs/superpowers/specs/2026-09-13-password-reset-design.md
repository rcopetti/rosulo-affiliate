# Password Reset via 6-Digit Email Code

**Date:** 2026-09-13
**Status:** Approved design, pending implementation plan

## Goal

Allow both user types — tenant users (admin portal) and affiliate accounts — to reset a
forgotten password via a 6-digit code emailed to them.

## User Flow

1. User clicks "Forgot password?" on the login page (affiliate `/login` or admin `/admin/login`).
2. User enters their email → backend emails a 6-digit code (valid 5 minutes).
3. User enters the code on a waiting/verification screen.
   - Correct → a short-lived reset token is issued; user proceeds to set a new password.
   - Wrong → up to 3 attempts total. On the 3rd wrong attempt the code is destroyed and
     the account is frozen for 5 minutes (`locked_until = now + 5min`).
4. After the freeze, the old code is dead — the user must request a fresh code.
5. A "Resend code" button on the verification screen re-requests a code; each new request
   invalidates the previous code.
6. New password accepted → user is sent back to the login page to sign in.

## Security Decisions

- **Silent 200 everywhere.** All public reset endpoints return generic success/errors that
  do not reveal whether an email is registered (anti-enumeration). This includes:
  - `request` returns 200 whether or not the email exists, and whether or not the account
    is locked (no email is sent in those cases, but the response is identical).
  - `verify` returns `invalid_or_expired_code` for unknown emails, expired codes,
    and wrong codes; `locked` only signals the freeze state (reachable for any email,
    so still non-enumerating).
- Codes are stored **hashed** (pbkdf2_sha256 via existing `pwd_context`), never plaintext.
- The reset token is an opaque random string; only its hash is stored.
- Reset does **not** invalidate existing JWTs (tokens are stateless; out of scope).

## Backend

### New model: `PasswordResetCode`

Table `password_reset_codes`, added via alembic migration:

| Column            | Type                        | Notes                                        |
|-------------------|-----------------------------|----------------------------------------------|
| id                | UUID PK                     |                                              |
| email             | String, indexed             |                                              |
| user_type         | String                      | `"tenant"` or `"affiliate"`                  |
| code_hash         | String                      | pbkdf2 hash of the 6-digit code              |
| attempts          | Integer, default 0          | wrong verify attempts on current code        |
| expires_at        | DateTime(tz)                | now + 5 min at creation                      |
| locked_until      | DateTime(tz), nullable      | freeze after 3 failed attempts               |
| reset_token_hash  | String, nullable            | set after successful verify                  |
| created_at        | DateTime(tz)                |                                              |

Unique constraint on `(email, user_type)` — one active reset per user. A new `request`
upserts/replaces the row (invalidating any previous code).

### Endpoints (new router `app/api/v1/auth/password_reset.py`, prefix `/auth/password-reset`)

**`POST /request`** `{email, user_type}`
- If `locked_until` is in the future → return 200, send nothing.
- Otherwise: generate `f"{secrets.randbelow(1_000_000):06d}"`, replace the row
  (`attempts=0`, fresh `expires_at`). Return 200.
- **Always create the row, even for unknown emails** (a "phantom" code that is never
  emailed). This keeps `verify`/`locked` behavior identical for registered and
  unregistered emails — otherwise `locked` would leak account existence. Email is
  sent only when a matching account exists; phantom rows can never reach `confirm`
  because there is no account to update (confirm fails generic on the 1-in-a-million
  chance the phantom code is guessed).

**`POST /verify`** `{email, user_type, code}`
- 200 `{reset_token}` on success: sets `reset_token_hash` on the row and extends
  `expires_at` to now + 10 min so the user has time to choose a password.
- 400 `{"detail": "invalid_or_expired_code"}` when: no row, expired row, or wrong
  code (attempts 1 and 2). Identical for unknown emails — no enumeration.
- 400 `{"detail": "locked"}` when `locked_until` is active, and on the attempt that
  triggers the lock. Lets the UI show freeze copy without revealing account existence.
- Each wrong attempt increments `attempts`. On the 3rd failure the code fields are
  cleared and `locked_until = now + 5min` is set.

**`POST /confirm`** `{email, user_type, reset_token, new_password}`
- 400 generic unless a row exists, `reset_token_hash` matches, and row is unexpired.
- On success: update `password_hash` on the matching account(s), delete the reset row.
- Tenant edge case: `TenantUser.email` is not globally unique (unique per tenant;
  login already assumes a single match). Confirm updates **all** `TenantUser` rows
  matching the email — consistent with the de-facto uniqueness assumption.

### Service: `app/services/password_reset.py`

- `request_code(db, email, user_type)` → generates/persists code, returns plaintext code
  or `None` (caller sends email only when not None; endpoint response is identical either way).
- `verify_code(db, email, user_type, code)` → returns reset token string, or raises
  `ValueError` (generic message).
- `confirm_reset(db, email, user_type, reset_token, new_password)` → updates password,
  or raises `ValueError`.

### Email

Add `send_password_reset_code(to, code)` to `app/services/email.py`, reusing
`send_email`. When `email_from` is not configured, log a warning and skip (same as
invite emails). Console backend prints the code to logs for local dev.

### Constants

- `CODE_TTL_MINUTES = 5`
- `VERIFIED_TTL_MINUTES = 10` (post-verify window to set a password)
- `MAX_ATTEMPTS = 3`
- `LOCKOUT_MINUTES = 5`

## Frontend

### New page: `ForgotPasswordPage`

Single component parameterized by `user_type`, mounted at two routes:
- `/forgot-password` → affiliate (`user_type="affiliate"`)
- `/admin/forgot-password` → tenant (`user_type="tenant"`)

Three steps in one component (local state machine):
1. **Email** — input + submit → request; always advances to step 2 (silent 200).
2. **Code** — 6-digit input + "Resend code" button. On verify success → step 3.
   On failure shows generic error; on 3rd failure shows "too many attempts, try again
   in 5 minutes" copy.
3. **New password** — password + confirm inputs → confirm; on success show a success
   message with a link back to the relevant login page.

### API client

- `src/api/auth.ts`: `requestPasswordReset`, `verifyPasswordResetCode`,
  `confirmPasswordReset` — three functions on the existing `api` axios instance,
  reused by both portals. `user_type` travels in the request body, so no separate
  admin client functions are needed (the reset endpoints are unauthenticated, so the
  only difference between `api`/`adminApi` — which token they attach — is irrelevant).

### Login pages

Add a "Forgot password?" link: `/login` → `/forgot-password`,
`/admin/login` → `/admin/forgot-password`.

## Testing

Backend (`tests/test_password_reset.py`, real test DB like existing tests):
- happy path: request → verify → confirm → login with new password works (affiliate and tenant)
- wrong code ×2 → verify fails, attempts tracked; ×3 → code dead + locked
- locked → request sends no new code, verify still 400; after `locked_until` passes, request works again
- expired code → verify 400
- resend → old code fails, new code works
- unknown email → request 200, no email sent
- confirm with bad/expired token → 400
- monkeypatch `send_email` / email service to capture the plaintext code

Frontend: component is straightforward state transitions; cover with existing
playwright/vitest conventions only if a matching test harness already exists for pages
(check `vitest.config.ts`/`playwright` usage before deciding).

## Out of Scope

- Invalidating existing JWT sessions on reset
- Rate limiting `request` beyond the lockout mechanism
- Admin-side (super-admin) password resets
