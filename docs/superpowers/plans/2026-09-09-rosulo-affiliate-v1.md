# Rosulo Affiliate v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI-based backend for the Rosulo Affiliate Service v1, including tenant/auth, click/lead/sale tracking, contract terms, commission calculation, tax withholding, payout request/approval, and PayPal execution.

**Architecture:** A Python FastAPI modular monolith backed by PostgreSQL. Business logic lives in `app/services/`. The API is split by role under `app/api/v1/admin/`, `app/api/v1/affiliate/`, and `app/api/v1/auth/`. Background work (payout PayPal calls, heavy event processing) is delegated to SQS workers. Authentication is built in: tenant API keys for `/v1/events` and admin endpoints; affiliate JWT for self-service endpoints. Affiliate accounts are global and can be linked to one or more tenants; all affiliate endpoints require an `X-Tenant-Id` header.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, Alembic, PostgreSQL, Amazon SQS, `boto3`, PayPal Payouts API, pytest, httpx, `python-jose`, `passlib`, uvicorn.

---

## Reference

Source spec: `docs/specs/2026-09-09-rosulo-affiliate-service-definition.md`

---

## File Structure

```
rosulo-affiliate/
├── pyproject.toml
├── README.md
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── alembic.ini
├── alembic/
│   └── versions/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   └── exceptions.py
│   ├── db/
│   │   ├── base.py
│   │   ├── session.py
│   │   ├── dependencies.py
│   │   └── models.py
│   ├── schemas/
│   │   ├── tenant.py
│   │   ├── affiliate.py
│   │   ├── affiliate_account.py
│   │   ├── contract.py
│   │   ├── campaign.py
│   │   ├── event.py
│   │   ├── commission.py
│   │   ├── payout.py
│   │   └── dashboard.py
│   ├── services/
│   │   ├── tenant.py
│   │   ├── affiliate.py
│   │   ├── affiliate_account.py
│   │   ├── contract.py
│   │   ├── campaign.py
│   │   ├── event.py
│   │   ├── commission.py
│   │   ├── payout.py
│   │   ├── tax.py
│   │   └── dashboard.py
│   ├── api/
│   │   └── v1/
│   │       ├── dependencies.py
│   │       ├── admin/
│   │       │   ├── affiliates.py
│   │       │   ├── contracts.py
│   │       │   ├── payouts.py
│   │       │   ├── events.py
│   │       │   └── dashboard.py
│   │       ├── affiliate/
│   │       │   ├── merchants.py
│   │       │   ├── profile.py
│   │       │   ├── campaigns.py
│   │       │   ├── balance.py
│   │       │   ├── payouts.py
│   │       │   └── dashboard.py
│   │       ├── auth/
│   │       │   └── affiliate.py
│   │       └── public/
│   │           ├── events.py
│   │           └── webhooks.py
│   ├── queue/
│   │   ├── client.py
│   │   ├── handlers.py
│   │   └── worker.py
│   └── integrations/
│       └── paypal.py
└── tests/
    ├── conftest.py
    ├── test_auth.py
    ├── test_affiliate.py
    ├── test_contract.py
    ├── test_campaign.py
    ├── test_events.py
    ├── test_commission.py
    ├── test_tax.py
    ├── test_payout.py
    └── test_dashboard.py
```

---

## Phase 1 — Bootstrap & Foundation

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `app/main.py`

**Steps:**

- [ ] **Step 1.1:** Add `pyproject.toml` with FastAPI, SQLAlchemy, Alembic, Pydantic, pytest, boto3, paypal-rest-sdk (or `httpx` for direct PayPal calls), `python-jose`, `passlib`.
- [ ] **Step 1.2:** Add `.env.example` with `DATABASE_URL`, `SQS_QUEUE_URL`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `SECRET_KEY`, `JWT_ALGORITHM`.
- [ ] **Step 1.3:** Add `Dockerfile` and `docker-compose.yml` for local Postgres.
- [ ] **Step 1.4:** Add `app/main.py` with the FastAPI app factory, health check, and v1 router prefix.

**Test:**
- Run: `uvicorn app.main:app --reload` and `curl http://localhost:8000/healthz` returns `200`.

### Task 2: Configuration, Database & Migrations

**Files:**
- Create: `app/core/config.py`
- Create: `app/db/base.py`
- Create: `app/db/session.py`
- Create: `app/db/dependencies.py`
- Create: `alembic.ini`
- Create: `app/db/models.py`

**Steps:**

- [ ] **Step 2.1:** Add `app/core/config.py` using Pydantic `BaseSettings` to load env vars.
- [ ] **Step 2.2:** Add SQLAlchemy `AsyncEngine`, `AsyncSession` in `app/db/session.py` and `get_db` dependency in `app/db/dependencies.py`.
- [ ] **Step 2.3:** Initialize Alembic and configure `alembic.ini` and `env.py` for async PostgreSQL.
- [ ] **Step 2.4:** Add `app/db/models.py` with the v1 entities:
  - `Tenant`
  - `AffiliateAccount` (global identity)
  - `Affiliate` (per-tenant link)
  - `AffiliateDocument`
  - `Contract`
  - `Term`
  - `Campaign`
  - `Event`
  - `PaymentRecord`
  - `Commission`
  - `Payout`
  - `PayoutCommission` association
- [ ] **Step 2.5:** Generate and run the initial Alembic migration.

**Test:**
- Run: `pytest tests/test_db.py -v` to verify a test DB can be created and the schema matches the models.

### Task 3: Authentication

**Files:**
- Create: `app/core/security.py`
- Create: `app/api/v1/dependencies.py`
- Create: `app/api/v1/auth/affiliate.py`

**Steps:**

- [ ] **Step 3.1:** Add `app/core/security.py` with tenant API key hash/verify and affiliate JWT create/verify helpers.
- [ ] **Step 3.2:** Add `app/api/v1/dependencies.py` with:
  - `get_tenant` (API key → tenant)
  - `get_tenant_admin` (tenant-scoped admin token)
  - `get_affiliate_account` (JWT → global `AffiliateAccount`)
  - `get_current_affiliate` (JWT + `X-Tenant-Id` → per-tenant `Affiliate`, rejecting access if the account is not linked to that tenant)
- [ ] **Step 3.3:** Add `app/api/v1/auth/affiliate.py` with `POST /v1/auth/affiliate/register` and `POST /v1/auth/affiliate/login`.
- [ ] **Step 3.4:** Add tests for all dependency paths, including cross-tenant rejection.

**Test:**
- Run: `pytest tests/test_auth.py -v`

---

## Phase 2 — Schemas & Basic CRUD

### Task 4: Pydantic Schemas

**Files:**
- Create: `app/schemas/tenant.py`, `affiliate.py`, `affiliate_account.py`, `contract.py`, `campaign.py`, `event.py`, `commission.py`, `payout.py`, `dashboard.py`

**Steps:**

- [ ] **Step 4.1:** Define request and response schemas for all public and admin endpoints.
- [ ] **Step 4.2:** Ensure schemas reflect the approved spec: `click`/`lead`/`sale` event types, one contract per affiliate, cross-campaign payouts.
- [ ] **Step 4.3:** Add tests that validate schema round-tripping from JSON.

### Task 5: Admin Affiliate & Contract Endpoints

**Files:**
- Create: `app/api/v1/admin/affiliates.py`
- Create: `app/api/v1/admin/contracts.py`
- Create: `app/services/affiliate.py`
- Create: `app/services/affiliate_account.py`
- Create: `app/services/contract.py`

**Steps:**

- [ ] **Step 5.1:** Implement `POST /v1/admin/affiliates` (create a global `AffiliateAccount` and a per-tenant `Affiliate` record with contract).
- [ ] **Step 5.2:** Implement `GET /v1/admin/affiliates`, `GET /v1/admin/affiliates/{id}`, `PATCH /v1/admin/affiliates/{id}`.
- [ ] **Step 5.3:** Implement `POST /v1/admin/affiliates/{id}/documents/approve` and `POST /v1/admin/affiliates/{id}/approve`.
- [ ] **Step 5.4:** Implement `GET/PUT /v1/admin/affiliates/{id}/contract` and `POST/PATCH` terms.
- [ ] **Step 5.5:** Add service-layer invariants from the spec (one active contract per affiliate per tenant, KYC gating).

**Test:**
- Run: `pytest tests/test_affiliate.py tests/test_contract.py -v`

### Task 6: Affiliate Campaign Endpoints

**Files:**
- Create: `app/api/v1/affiliate/campaigns.py`
- Create: `app/services/campaign.py`

**Steps:**

- [ ] **Step 6.1:** Implement `POST /v1/affiliate/campaigns`, `GET /v1/affiliate/campaigns`, `GET /v1/affiliate/campaigns/{id}`, `PATCH /v1/affiliate/campaigns/{id}`.
- [ ] **Step 6.2:** Enforce that the affiliate id comes from the JWT + `X-Tenant-Id`, not from URL.

**Test:**
- Run: `pytest tests/test_campaign.py -v`

### Task 6.5: Affiliate Tenant Selection & Profile

**Files:**
- Create: `app/api/v1/affiliate/merchants.py`
- Create: `app/api/v1/affiliate/profile.py`
- Create: `app/services/affiliate_account.py`

**Steps:**

- [ ] **Step 6.5.1:** Implement `GET /v1/affiliate/merchants` to list tenants the account is linked to.
- [ ] **Step 6.5.2:** Implement `POST /v1/affiliate/merchants/{tenant_id}/join` (request/accept invite to a tenant).
- [ ] **Step 6.5.3:** Implement `GET /v1/affiliate/profile` and `PATCH /v1/affiliate/profile` for the global account.
- [ ] **Step 6.5.4:** Add tests for multi-merchant access and cross-tenant rejection.

**Test:**
- Run: `pytest tests/test_affiliate.py -v`

---

## Phase 3 — Tracking, Commission & Tax

### Task 7: Event Ingestion

**Files:**
- Create: `app/api/v1/public/events.py`
- Create: `app/services/event.py`

**Steps:**

- [ ] **Step 7.1:** Implement `POST /v1/events` for `click`, `lead`, and `sale` events.
- [ ] **Step 7.2:** Enforce idempotency by `event_id` or deterministic idempotency key.
- [ ] **Step 7.3:** Validate `campaign_id` belongs to the affiliate on `click`/`lead` and resolve affiliate from campaign.
- [ ] **Step 7.4:** Implement the `sale` event payload validation, including `good_date` and `payment_record_id`.

**Test:**
- Run: `pytest tests/test_events.py -v`

### Task 8: Payment Record & Good Date Availability

**Files:**
- Create: `app/services/payment_record.py` (or extend `app/services/event.py`)
- Modify: `app/db/models.py` as needed

**Steps:**

- [ ] **Step 8.1:** Implement `PaymentRecord` upsert from tenant webhook.
- [ ] **Step 8.2:** Link pending sale events to `PaymentRecord` by `payment_record_id`.
- [ ] **Step 8.3:** Mark commissions as `available` only when `good_date <= today` and a matching `PaymentRecord` exists.
- [ ] **Step 8.4:** Keep unlinked sale events as `coming revenue`.

**Test:**
- Run: `pytest tests/test_payment_record.py -v` (create if needed)

### Task 9: Commission Calculation

**Files:**
- Create: `app/services/commission.py`

**Steps:**

- [ ] **Step 9.1:** On `sale` event, look up the affiliate's active contract and matching term by `payment_sequence`.
- [ ] **Step 9.2:** Calculate `gross_amount` from term's `commission_percent`.
- [ ] **Step 9.3:** If the sequence is not covered, record the sale but do not create a commission.
- [ ] **Step 9.4:** On `refunded`/`charged_back` `PaymentRecord`, create a negative commission reversal.
- [ ] **Step 9.5:** Apply reversals to the affiliate balance, even if the original commission was already paid.

**Test:**
- Run: `pytest tests/test_commission.py -v`

### Task 10: Tax Withholding

**Files:**
- Create: `app/services/tax.py`
- Modify: `app/services/commission.py`

**Steps:**

- [ ] **Step 10.1:** Add `TaxService` that applies the configured rate based on affiliate `tax_status`, `backup_withholding_required`, and country.
- [ ] **Step 10.2:** Support tenant overrides (per-country / per-status tables).
- [ ] **Step 10.3:** Compute `withholding_amount` and `net_amount` on each commission.
- [ ] **Step 10.4:** Add tests for US person 0%/24% and non-US 30% treaty cases.

**Test:**
- Run: `pytest tests/test_tax.py -v`

---

## Phase 4 — Payouts & Dashboard

### Task 11: Payout Request & Approval

**Files:**
- Create: `app/api/v1/affiliate/payouts.py`
- Create: `app/api/v1/admin/payouts.py`
- Create: `app/services/payout.py`

**Steps:**

- [ ] **Step 11.1:** Implement `POST /v1/affiliate/payout-requests`.
- [ ] **Step 11.2:** Aggregate available commissions cross-campaign into a `Payout` in `requested` status.
- [ ] **Step 11.3:** Block the request if KYC is not approved.
- [ ] **Step 11.4:** Implement `POST /v1/admin/payouts/{id}/approve` and `/reject`.
- [ ] **Step 11.5:** On approval, enqueue an SQS message to execute the PayPal payout.

**Test:**
- Run: `pytest tests/test_payout.py -v`

### Task 12: PayPal Integration

**Files:**
- Create: `app/integrations/paypal.py`
- Create: `app/queue/handlers.py`
- Create: `app/queue/worker.py`

**Steps:**

- [ ] **Step 12.1:** Add `app/integrations/paypal.py` with PayPal Payouts API client.
- [ ] **Step 12.2:** Implement `app/queue/handlers.py` to process the payout SQS message.
- [ ] **Step 12.3:** On PayPal success, mark the payout `paid` and commissions `paid`.
- [ ] **Step 12.4:** On failure, mark the payout `failed` and restore commission status to `available`.
- [ ] **Step 12.5:** Add idempotency: do not process the same `payout_id` twice.

**Test:**
- Run: `pytest tests/test_paypal.py -v` (create if needed) or mock PayPal calls in `tests/test_payout.py`.

### Task 13: Dashboard Aggregations

**Files:**
- Create: `app/api/v1/affiliate/dashboard.py`
- Create: `app/api/v1/admin/dashboard.py`
- Create: `app/services/dashboard.py`

**Steps:**

- [ ] **Step 13.1:** Affiliate dashboard: lead volume by day/hour, sales grouped by payment sequence, balance, payout history.
- [ ] **Step 13.2:** Tenant dashboard: campaign performance (clicks, leads, conversion), affiliate status, commission liability, payout queue.
- [ ] **Step 13.3:** Optimize with materialized query or in-memory aggregation; v1 can use SQL `GROUP BY` unless volume demands more.

**Test:**
- Run: `pytest tests/test_dashboard.py -v`

---

## Phase 5 — Webhooks, Queue & Deployment

### Task 14: Webhooks & Queue

**Files:**
- Create: `app/api/v1/public/webhooks.py`
- Create: `app/queue/client.py`
- Modify: `app/queue/worker.py`

**Steps:**

- [ ] **Step 14.1:** Implement `POST /v1/webhooks/tenant` to receive payment records from allbum.me / tenants.
- [ ] **Step 14.2:** Implement `POST /v1/webhooks/paypal` for PayPal IPN / payout status updates.
- [ ] **Step 14.3:** Implement `app/queue/client.py` to publish SQS messages.
- [ ] **Step 14.4:** Add a local worker entry point that polls SQS (or a local in-memory queue for dev) and calls the handler.

**Test:**
- Run: `pytest tests/test_webhooks.py -v` (create if needed)

### Task 15: AWS App Runner Deployment

**Files:**
- Create: `apprunner.yaml`
- Create: `scripts/entrypoint.sh`
- Modify: `Dockerfile`

**Steps:**

- [ ] **Step 15.1:** Finalize `Dockerfile` for App Runner.
- [ ] **Step 15.2:** Add `apprunner.yaml` with build/run settings and env var placeholders.
- [ ] **Step 15.3:** Add `scripts/entrypoint.sh` that runs migrations before starting the app.
- [ ] **Step 15.4:** Document the deployment steps in `README.md`.

**Test:**
- Run: `docker build -t rosulo-affiliate .` and `docker run -p 8000:8000 rosulo-affiliate` returns a healthy container.

---

## Self-Review

**Spec coverage:**
- Multi-tenant tenant + affiliate accounts: Tasks 2, 3, 5, 6.5.
- One contract per affiliate with terms by payment sequence: Tasks 5, 9.
- Affiliate-created campaigns: Task 6.
- Click/lead/sale event tracking: Tasks 7, 8.
- Payment record / good date / coming revenue: Task 8.
- Commission calculation and refunds: Task 9.
- Tax withholding (US/non-US): Task 10.
- Payout request/approval + PayPal: Tasks 11, 12.
- Affiliate + tenant dashboards: Task 13.
- SQS background jobs: Task 14.
- FastAPI / AWS App Runner: Tasks 1, 15.

**Placeholder scan:** No TBD/TODO in task descriptions. Each task names the files and the expected test command.

**Type consistency:** Models and schemas must share field names (e.g. `click`/`lead`/`sale` types, `good_date`, `payment_sequence`, `withholding_amount`, `net_paid`). This is enforced by Pydantic/SQLAlchemy shared definitions in Task 4 and Task 2.

---

## Execution Options

Plan complete and saved to `docs/superpowers/plans/2026-09-09-rosulo-affiliate-v1.md`.

**1. Subagent-Driven (recommended):** Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution:** Execute tasks in this session using `executing-plans`, with checkpoint reviews.

Which approach do you want?
