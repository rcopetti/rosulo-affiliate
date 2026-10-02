# Merchant Manual Payout Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let merchants inspect and decide itemized commission-backed payouts, manually record completed PayPal payments as `PayoutPayment`, see payout history/totals by affiliate, and deliver an observable affiliate email notice.

**Architecture:** Extend the W0.2 manual settlement foundation after the commission-selection plan has landed. Replace payout use of the overloaded incoming `PaymentRecord` with an outgoing `PayoutPayment`, preserving payout-linked rows and failing closed if incoming rows exist until retention is resolved. Store a payout email-notification record in the same transaction as payment, attempt email after commit, expose retryable delivery state, and scan pending notifications from the scheduled maintenance job introduced by the prerequisite plan.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 async, PostgreSQL, Alembic, AWS SES, AWS ECS/Fargate, React, TypeScript, TanStack Query, Vitest, pytest.

---

## Prerequisites and dependency

- Execute `docs/superpowers/plans/2026-10-01-commission-availability-and-request-implementation-plan.md` first. This plan depends on its `Commission.status="reserved"`, `PayoutCommission.is_active`, `available_at`, server-side commission selection, and daily Fargate maintenance task.
- The expected Alembic parent revision is `e8f9a0b1c2d3`. Confirm `uv run --no-sync alembic history` before generating the new migration.
- Keep `Event.payment_record_id` as the merchant's external sale/refund correlation string. Do not use or recreate an incoming `PaymentRecord` dependency.
- Preserve payout-linked rows from the current W0.2 `payment_records` table. The migration must stop before dropping the table if any `record_type='incoming_payment'` row exists; the service owner must resolve export/archive retention before re-running that migration.
- The `payout_scenario` test fixture and isolated `TEST_DATABASE_URL` introduced by the prerequisite plan are reused here. `backend/tests/conftest.py` drops/recreates its configured test database; use a disposable PostgreSQL database only.
- Preserve an expand/contract deployment order: apply `f9a0b1c2d3e4` while legacy tables still exist, deploy the new App Runner image and wait for all old instances to drain, then run `a1b2c3d4e5f6` to drop legacy fields/tables. Schedule a short merchant payout maintenance window during the App Runner rollout; do not initiate or confirm external PayPal transfers until the new service version is healthy.

## File map

| File | Responsibility in this plan |
|---|---|
| `backend/app/db/models.py` | Add `PayoutPayment` and `PayoutNotification`; retain the legacy `PaymentRecord` mapping until its retirement migration |
| `backend/alembic/versions/f9a0b1c2d3e4_payout_payment_and_notifications.py` | Create new payment/notification tables and copy payout-linked rows while preserving the legacy table |
| `backend/alembic/versions/a1b2c3d4e5f6_retire_incoming_payment_records.py` | Fail closed on unresolved incoming rows, then drop legacy payment storage and unused batch field |
| `backend/app/services/payout.py` | Confirm actual PayPal payment datetime/reference, create payment and notification atomically, maintain transition and commission states |
| `backend/app/schemas/payout.py` | Return affiliate/payee identity, itemized commission/source-sale data, `PayoutPayment`, and notification state |
| `backend/app/api/v1/admin/payouts.py`, `backend/app/api/v1/affiliate/payouts.py`, `backend/app/api/v1/admin/affiliates.py` | Tenant-scoped detail, approval, rejection, confirmation, notification retry, affiliate payout history and totals |
| `backend/app/services/affiliate.py`, `backend/app/services/dashboard.py` | Return merchant payout history and paid totals by currency and date window |
| `backend/app/services/payment_record.py`, `backend/app/api/v1/public/webhooks.py`, `backend/app/services/event.py` | Retire incoming-payment persistence; keep event correlation identifier independent |
| `backend/app/integrations/paypal.py`, `backend/app/core/config.py`, `backend/.env.example`, `README.md` | Remove unused PayPal API-dispatch credentials/client and document manual PayPal settlement only |
| `backend/app/services/email.py`, `backend/app/templates/email/payout_paid.html`, `backend/app/templates/email/payout_paid.txt` | Render/send paid payout email with authenticated detail link |
| `backend/app/jobs/payout_maintenance.py`, `backend/deployment/payout-maintenance.yaml` | Recover notification outbox rows and grant the Fargate task scoped SES send access |
| `backend/tests/test_payout.py`, `backend/tests/test_dashboard.py`, `backend/tests/test_events.py`, `backend/tests/test_document_review_migration.py` | Verify settlement, histories, retired webhook, and revision chain |
| `backend/tests/test_payout_payment_migration.py`, `backend/tests/test_payout_notification.py`, `backend/tests/test_email.py` | New migration, delivery, and email tests |
| `frontend/src/api/types.ts`, `frontend/src/api/admin/payouts.ts`, `frontend/src/api/admin/affiliates.ts`, `frontend/src/api/affiliate/payouts.ts` | Typed itemized detail, actual payment fields, history/summary, notification retry |
| `frontend/src/components/admin/PayoutQueue.tsx`, `frontend/src/components/admin/PayoutDetail.tsx`, `frontend/src/components/shared/PayoutStatusBadge.tsx`, `frontend/src/pages/admin/PayoutsPage.tsx`, `frontend/src/pages/admin/AffiliateDetailPage.tsx` | Merchant review, PayPal confirmation modal, affiliate history and paid totals |
| `frontend/src/pages/affiliate/PayoutsPage.tsx`, `frontend/src/pages/affiliate/PayoutDetailPage.tsx`, `frontend/src/components/affiliate/PayoutsTable.tsx`, `frontend/src/router.tsx`, `frontend/src/pages/LoginPage.tsx`, `frontend/src/pages/affiliate/MerchantSelectPage.tsx`, `frontend/src/api/auth.ts` | Authenticated payout deep link and safe login/merchant-selection return path |
| `frontend/src/tests/components/PayoutQueue.test.tsx`, `frontend/src/tests/components/PayoutsTable.test.tsx`, `frontend/src/tests/pages/AffiliateDetailPage.test.tsx`, `frontend/src/tests/pages/PayoutDetailPage.test.tsx` | Merchant and affiliate UI behavior |

## Task 1: Add payout-specific payment/notification models and safe migration

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/f9a0b1c2d3e4_payout_payment_and_notifications.py`
- Modify: `backend/tests/test_document_review_migration.py`
- Create: `backend/tests/test_payout_payment_migration.py`

- [ ] **Step 1: Add failing model and migration-chain tests**

Add tests asserting `PayoutPayment.__tablename__ == "payout_payments"`, one `payout_id` per payment, `PayoutNotification.__tablename__ == "payout_notifications"`, and the migration parent is `e8f9a0b1c2d3`.

- [ ] **Step 2: Run the new tests and confirm they fail**

Run from `backend/`:

```bash
uv run pytest tests/test_document_review_migration.py tests/test_payout_payment_migration.py -q
```

Expected before implementation: FAIL because the models and revision do not exist.

- [ ] **Step 3: Define the outgoing payment and notification rows**

In `backend/app/db/models.py`, add:

- `PayoutPayment`: UUID primary key; unique non-null `payout_id`; `amount NUMERIC(20,2)`; `currency`; `payment_method` (new confirmations use `paypal`); required `transfer_reference`; timezone-aware `paid_at`; required `recorded_by_tenant_user_id`; `created_at`; relationships to `Payout` and `TenantUser`.
- `PayoutNotification`: UUID primary key; unique non-null `payout_id`; status `pending | sending | sent | failed`; `attempt_count` default zero; `last_attempt_at`, `lease_expires_at`, `sent_at`, `last_error`, `created_at`, `updated_at`; relationship to `Payout`. `sending` is a leased claim so a crashed process can be recovered.
- Add a Payout `CheckConstraint` permitting only `pending_approval`, `approved`, `rejected`, and `paid`; set the ORM and database default to `pending_approval`.
- Add a `payout_payment` relationship and a notification relationship to `Payout`; keep the legacy `payment_record` relationship temporarily so existing rows remain mapped.
- Keep the `PaymentRecord` ORM model and `Payout.paypal_batch_id` field temporarily so the existing table/column remains mapped while incoming ingestion is retired and payout writes move to `PayoutPayment`. Remove those legacy mappings only in Task 7 after the retirement migration is ready.

Do not snapshot the PayPal recipient in `PayoutPayment`; the required audit record is amount/currency, actual payment time, transaction/reference, and confirming user. The recipient stays in the affiliate profile and is displayed in the merchant confirmation UI.

- [ ] **Step 4: Create revision `f9a0b1c2d3e4` with data-preserving conversion**

Create `backend/alembic/versions/f9a0b1c2d3e4_payout_payment_and_notifications.py` with `down_revision = "e8f9a0b1c2d3"`. In `upgrade()`:

1. Preflight that every `payment_records.record_type='affiliate_payout'` row has a payout ID, reference, method, amount, currency, paid time, and recorded actor; abort with an actionable error if any required value is missing.
2. Preflight `SELECT 1 FROM payment_records WHERE record_type NOT IN ('incoming_payment', 'affiliate_payout') LIMIT 1`; abort on an unknown record type.
3. Create `payout_payments` with one row per payout, using a unique constraint on `payout_id`.
4. Copy every `affiliate_payout` payment row into `payout_payments`, preserving IDs, payout IDs, amount, currency, payment method, reference, paid time, and confirming user. Assert source and destination row counts match; keep `payment_records` intact for the separate retirement gate in Task 7.
5. Create `payout_notifications` with a unique payout ID and `pending | sending | sent | failed` status constraint plus `lease_expires_at` for crashed-send recovery.
6. Add the database check constraint for payout states `pending_approval`, `approved`, `rejected`, `paid`, and change the server default to `pending_approval`; preflight in the prerequisite migration ensures no unsupported status remains.

In `downgrade()`, fail closed if any `PayoutPayment` or `PayoutNotification` row exists; do not silently delete payment or email delivery history.

- [ ] **Step 5: Verify the new migration chain and model fields**

Run from `backend/`:

```bash
uv run pytest tests/test_document_review_migration.py tests/test_payout_payment_migration.py tests/test_money_models.py -q
```

Expected: PASS; current Alembic head is `f9a0b1c2d3e4`, `PayoutPayment.amount` uses `NUMERIC(20,2)`, and the payout payment uniqueness constraint is present.

- [ ] **Step 6: Commit the persistence change**

```bash
git add backend/app/db/models.py backend/alembic/versions/f9a0b1c2d3e4_payout_payment_and_notifications.py backend/tests/test_document_review_migration.py backend/tests/test_payout_payment_migration.py backend/tests/test_money_models.py
git commit -m "Separate affiliate payout payment records"
```

## Task 2: Retire incoming-payment and automatic PayPal execution paths

**Files:**
- Modify: `backend/app/api/v1/public/webhooks.py`, `backend/app/services/event.py`, `backend/app/core/config.py`, `backend/app/queue/client.py`, `backend/.env.example`, `README.md`
- Delete: `backend/app/services/payment_record.py`, `backend/app/integrations/paypal.py`
- Modify: `backend/tests/test_events.py`, `backend/tests/test_payout.py`

- [ ] **Step 1: Add failing tests for retired ingestion and retained event ID**

Add API tests that `POST /api/v1/webhooks/tenant` returns 410 with an explicit retired-endpoint message, a `sale` event still accepts and stores its external `payment_record_id`, and the sale event's `good_date` controls commission availability without any incoming-payment webhook call.

- [ ] **Step 2: Run the tests and confirm the old webhook behavior fails them**

Run from `backend/`:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_events.py tests/test_payout.py -k 'payment_record or webhook or good_date' -q
```

Expected before implementation: FAIL because the tenant webhook currently upserts an incoming `PaymentRecord`.

- [ ] **Step 3: Return 410 from the retired tenant webhook**

In `backend/app/api/v1/public/webhooks.py`, replace the tenant webhook's upsert behavior with `HTTPException(status_code=410, detail="Incoming payment-record webhooks are retired; send a confirmed sale event")`. Keep the PayPal payout webhook's existing 410. Remove the import/use of `payment_service`, remove the unused `PaymentRecord` import from `backend/app/services/event.py`, and delete `backend/app/services/payment_record.py` after all runtime imports are removed. Delete `backend/app/integrations/paypal.py` and remove `paypal_client_id`, `paypal_client_secret`, and `paypal_base_url` from `backend/app/core/config.py` and `backend/.env.example`; remove the PayPal API credential/sandbox setup instructions from `README.md`. Delete the unused `publish_payout` function from `backend/app/queue/client.py` so no application path can enqueue a new transfer. Keep `handle_payout` as a no-op while the existing worker drains any stale SQS payout messages.

- [ ] **Step 4: Keep `Event.payment_record_id` as an external identifier only**

Retain the nullable string field in `Event` and its event API response. Do not add a foreign key to `PayoutPayment` or require a Rosulo payment row when creating a sale commission. Add a test proving the supplied value is stored verbatim on the sale Event. In `backend/tests/test_payout.py`, remove the monkeypatch of `app.integrations.paypal.send_payout`; keep the stale `handle_payout` message test and assert it leaves an approved payout and reserved commissions unchanged.

- [ ] **Step 5: Run event and payout tests**

Run from `backend/`:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_events.py tests/test_payout.py -q
```

Expected: PASS; incoming-payment ingestion is explicitly retired and sale/refund correlation data remains on Event.

- [ ] **Step 6: Commit the retired incoming endpoint**

```bash
git add backend/app/api/v1/public/webhooks.py backend/app/services/payment_record.py backend/app/services/event.py backend/app/integrations/paypal.py backend/app/core/config.py backend/app/queue/client.py backend/.env.example README.md backend/tests/test_events.py backend/tests/test_payout.py
git commit -m "Retire incoming and automatic payout integrations"
```

## Task 3: Record actual PayPal payment datetime and preserve payout state atomically

**Files:**
- Modify: `backend/app/schemas/payout.py`
- Modify: `backend/app/services/payout.py`
- Modify: `backend/app/api/v1/admin/payouts.py`
- Modify: `backend/tests/test_payout.py`

- [ ] **Step 1: Add failing payment confirmation tests**

Using `payout_scenario`, test that the confirmation request requires timezone-aware `paid_at` and a nonblank PayPal reference; an approved payout records `PayoutPayment.payment_method == "paypal"`, uses `Payout.net_paid` and currency (not client values), and stores merchant-entered `paid_at`; identical retries return the existing record; conflicting retries return 409; pending/rejected payouts cannot be marked paid.

- [ ] **Step 2: Run focused tests and confirm the old API contract fails**

Run from `backend/`:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_payout.py -k 'payment_confirmation or confirm_payment' -q
```

Expected before implementation: FAIL because the current schema accepts generic `payment_method` and server confirmation time only.

- [ ] **Step 3: Change the request/response schema**

Change `PayoutPaymentConfirmation` to accept `paid_at: datetime` and `transfer_reference`; forbid extra fields so callers cannot override amount/currency/method. Validate `paid_at` contains an offset and is not later than the current UTC time; trim and reject a blank reference. Replace `PayoutOut.payment_record` with `payout_payment: PayoutPaymentOut | None`.

- [ ] **Step 4: Create the payment and notification atomically**

Update `confirm_payout_payment` to lock the payout and all linked commissions in deterministic ID order; require payout `approved`, every link to reference this payout, and every commission to be `reserved` or to be a legacy `pending` row linked to an active `pending_approval`/`approved` payout. New requests use `reserved`/`is_active=true`; legacy pending rows are accepted only during the expand/contract rollout. On success, in one transaction:

1. Create one `PayoutPayment` with fixed method `paypal`, `payout.net_paid`, `payout.currency`, merchant-supplied UTC `paid_at`, trimmed PayPal reference, and confirming tenant user. Remove the `PaymentRecord` import/write from `payout.py`; keep only the ORM/table mapping until Task 7's contract migration, and do not query legacy incoming records as customer payment evidence.
2. Create one `PayoutNotification(status="pending")` for the payout.
3. Set payout status/`paid_at` to `paid`/provided time; set commissions to `paid`; set links `is_active=false`; append the ordered `approved -> paid` transition.
4. Commit all rows together.

For an already-paid payout, return the existing result only if stored `paid_at` and reference exactly match. Otherwise return 409 without mutation.

- [ ] **Step 5: Pass the merchant-entered datetime from the API**

Update `POST /api/v1/admin/payouts/{payout_id}/confirm-payment` to pass `data.paid_at` and `data.transfer_reference`; do not accept a payment method, amount, or currency from the browser.

- [ ] **Step 6: Verify atomicity, idempotency, and error branches**

Run from `backend/`:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_payout.py -k 'payment or approved or rejected or reservation' -q
```

Expected: PASS; failures leave the payout approved with commissions reserved and no partial `PayoutPayment`/notification records.

- [ ] **Step 7: Commit PayPal confirmation behavior**

```bash
git add backend/app/schemas/payout.py backend/app/services/payout.py backend/app/api/v1/admin/payouts.py backend/tests/test_payout.py
git commit -m "Record merchant-confirmed PayPal payment dates"
```

## Task 4: Return complete itemized payout detail and merchant PayPal instructions

**Files:**
- Modify: `backend/app/schemas/payout.py`, `backend/app/services/payout.py`, `backend/app/api/v1/admin/payouts.py`
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/admin/payouts.ts`
- Modify: `frontend/src/components/admin/PayoutDetail.tsx`, `frontend/src/components/admin/PayoutQueue.tsx`, `frontend/src/components/shared/PayoutStatusBadge.tsx`, `frontend/src/pages/admin/PayoutsPage.tsx`
- Modify: `backend/tests/test_payout.py`, `frontend/src/tests/components/PayoutQueue.test.tsx`

- [ ] **Step 1: Add failing API and component tests**

Test that merchant payout detail contains affiliate `name`, `email`, and `paypal_email`, plus each linked commission's ID, source sale `Event.occurred_at`, `good_date`, payment sequence, gross, withholding, net, and currency. Assert returned count/date range/totals reconcile to lines. Update the modal test to assert it displays those affiliate fields, net payout amount/currency, commission count, and only accepts `paid_at` and PayPal reference.

- [ ] **Step 2: Run payout detail tests and confirm the missing fields**

Run from repository root:

```bash
cd backend && TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_payout.py -k 'detail or itemized' -q
cd ../frontend && npm run test -- src/tests/components/PayoutQueue.test.tsx
```

Expected before implementation: API response lacks commission lines/payee identity; UI accepts generic payment method and has no paid datetime.

- [ ] **Step 3: Extend payout response schema and tenant-scoped loading**

Add `PayoutCommissionDetailOut` with `commission_id`, `event_id`, `occurred_at`, `good_date`, `payment_sequence`, `gross_amount`, `withholding_amount`, `net_amount`, `currency`, and campaign ID. Return these under `payout_commissions`; compute count and min/max source sale `occurred_at` from linked rows. Load affiliate/account and commission/event relationships with `selectinload` in tenant-scoped `get_payout`; never expose cross-tenant payout existence. Update `PayoutOut.status` to `pending_approval | approved | rejected | paid`, replace `payment_record` with `payout_payment`, and remove `paypal_batch_id` from API/TypeScript DTOs.

- [ ] **Step 4: Build the approval detail view**

Show all commission rows, count, source-sale date range, gross/withholding/net totals, affiliate name/contact email/PayPal email, status, and transition history. Leave commission amounts and selected membership read-only. Make `PayoutQueue` open the detail for pending requests before approval/rejection. Update `PayoutStatusBadge` to display only `pending_approval`, `approved`, `rejected`, or `paid`; remove old `requested`, `processing`, and `failed` states from active UI types.

- [ ] **Step 5: Replace the generic modal with PayPal confirmation**

In `PayoutQueue`, show the existing affiliate PayPal email and exact `net_paid`/currency, then collect `paid_at` using `datetime-local` and the required PayPal transaction/reference. Convert the browser-local value to an ISO-8601 offset timestamp before API submission. Do not let the merchant edit payout amount, commission membership, method, or currency.

- [ ] **Step 6: Run backend/frontend focused tests and build**

Run:

```bash
cd backend && TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_payout.py -k 'detail or payment' -q
cd ../frontend && npm run test -- src/tests/components/PayoutQueue.test.tsx && npm run build
```

Expected: payout lines and payee fields match API fixtures; invalid/blank datetime/reference blocks confirmation; build succeeds.

- [ ] **Step 7: Commit itemized merchant review**

```bash
git add backend/app/schemas/payout.py backend/app/services/payout.py backend/app/api/v1/admin/payouts.py backend/tests/test_payout.py frontend/src/api/types.ts frontend/src/api/admin/payouts.ts frontend/src/components/admin/PayoutDetail.tsx frontend/src/components/admin/PayoutQueue.tsx frontend/src/components/shared/PayoutStatusBadge.tsx frontend/src/pages/admin/PayoutsPage.tsx frontend/src/tests/components/PayoutQueue.test.tsx
git commit -m "Show commission lines before merchant payout approval"
```

## Task 5: Add affiliate payout history and paid totals to merchant affiliate detail

**Files:**
- Modify: `backend/app/api/v1/admin/affiliates.py`, `backend/app/schemas/affiliate.py`, `backend/app/services/payout.py`
- Modify: `frontend/src/api/admin/affiliates.ts`, `frontend/src/pages/admin/AffiliateDetailPage.tsx`
- Modify: `backend/tests/test_dashboard.py`, `backend/tests/test_payout.py`, `frontend/src/tests/pages/AffiliateDetailPage.test.tsx`

- [ ] **Step 1: Add failing aggregate and tenant-isolation tests**

Seed paid and unpaid payouts for two currencies and payment datetimes on each side of the rolling-12-month and current-year boundaries. Test `GET /api/v1/admin/affiliates/{affiliate_id}/payouts?limit=20&offset=0` returns only the authenticated tenant's affiliate history, paginated items, and `paid_totals_by_currency` with `rolling_12_months` and `year_to_date`. Confirm pending/approved/rejected payouts do not contribute to paid totals.

- [ ] **Step 2: Run the focused tests and confirm the endpoint is absent**

Run from `backend/`:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_payout.py tests/test_dashboard.py -k 'affiliate_payout_history or paid_totals' -q
```

Expected before implementation: FAIL because the affiliate payout-history endpoint and aggregate fields do not exist.

- [ ] **Step 3: Implement payment-date aggregation**

Add a payout service query scoped by both `affiliate_id` and `tenant_id`. Group `PayoutPayment.amount` by currency for `paid_at >= one_year_ago_utc` and `paid_at >= UTC Jan 1 of the current year`; define one year ago by replacing the UTC year with `year - 1` and use February 28 when the prior year has no February 29. Never sum across currencies. Return payout rows newest-first with a maximum `limit=100` and validated nonnegative `offset`.

- [ ] **Step 4: Add the tenant-scoped API and schema**

Add `GET /api/v1/admin/affiliates/{affiliate_id}/payouts` in `backend/app/api/v1/admin/affiliates.py`. Return `{items, total, limit, offset, paid_totals_by_currency}`; return 404 for a missing or cross-tenant affiliate.

- [ ] **Step 5: Render payout history and totals in affiliate detail**

In `AffiliateDetailPage`, query the new endpoint and show per-currency rolling 12-month/YTD paid totals plus a paginated payout history containing requested/paid dates, status, gross/net, currency, and payment reference when present. Do not label the paid payout aggregate “earned commissions.”

- [ ] **Step 6: Run aggregate, UI, and build checks**

Run:

```bash
cd backend && TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_payout.py tests/test_dashboard.py -k 'affiliate_payout_history or paid_totals' -q
cd ../frontend && npm run test -- src/tests/pages/AffiliateDetailPage.test.tsx && npm run build
```

Expected: all currencies remain separate and totals match only `PayoutPayment` rows in each specified period.

- [ ] **Step 7: Commit merchant payout history**

```bash
git add backend/app/api/v1/admin/affiliates.py backend/app/schemas/affiliate.py backend/app/services/payout.py backend/tests/test_dashboard.py backend/tests/test_payout.py frontend/src/api/admin/affiliates.ts frontend/src/pages/admin/AffiliateDetailPage.tsx frontend/src/tests/pages/AffiliateDetailPage.test.tsx
git commit -m "Report affiliate paid payout history by currency"
```

## Task 6: Deliver an observable payout email with retry

**Files:**
- Modify: `backend/app/api/v1/admin/payouts.py`, `backend/app/services/payout.py`, `backend/app/services/email.py`
- Create: `backend/app/templates/email/payout_paid.html`, `backend/app/templates/email/payout_paid.txt`
- Modify: `backend/app/jobs/payout_maintenance.py`
- Modify: `backend/app/schemas/payout.py`, `frontend/src/api/types.ts`, `frontend/src/api/admin/payouts.ts`
- Modify: `frontend/src/components/admin/PayoutDetail.tsx`, `frontend/src/pages/affiliate/PayoutsPage.tsx`, `frontend/src/router.tsx`
- Create: `frontend/src/pages/affiliate/PayoutDetailPage.tsx`
- Create: `backend/tests/test_email.py`, `backend/tests/test_payout_notification.py`, `frontend/src/tests/pages/PayoutDetailPage.test.tsx`

- [ ] **Step 1: Add failing notification and email-template tests**

Test that payment commit creates one pending notification; successful render includes affiliate name, payout amount/currency, PayPal reference, and payout URL; a send exception records `failed` without changing the paid payout; repeated payment confirmation does not create a second notification; one of two concurrent workers claims a notification; an expired `sending` lease is recovered by the maintenance job; merchant retry changes a failed notification to sent after a successful send.

- [ ] **Step 2: Run notification tests and confirm they fail**

Run from `backend/`:

```bash
uv run pytest tests/test_email.py tests/test_payout_notification.py -q
```

Expected before implementation: no payout email renderer, notification delivery state, or retry path exists.

- [ ] **Step 3: Implement the payout email template and sender**

Add `render_email("payout_paid", ...)` and `send_payout_paid_email(...)` in `backend/app/services/email.py`, following `invite` and `password_reset` conventions. Build the link from `settings.frontend_url.rstrip("/")` plus `/affiliate/payouts/{payout_id}?tenant_id={payout.tenant_id}`; tenant ID and payout UUID are non-secret routing context, not authorization. Never put a token, email address, or payment secret in the URL. Configure the SES boto3 client with `botocore.config.Config(connect_timeout=5, read_timeout=15, retries={"total_max_attempts": 1})`; record the failure state for application/operator retry rather than hiding provider retries inside the client.

- [ ] **Step 4: Send after payment commit and persist delivery status**

The confirmation endpoint must add a FastAPI `BackgroundTasks` job only after `confirm_payout_payment` commits. The task opens a fresh `async_session`, atomically claims a `pending` notification as `sending` with `lease_expires_at = now_utc + 10 minutes` and increments `attempt_count`, then commits the claim before calling SES. After provider acceptance, set `sent`/`sent_at`; on error set `failed`/`last_error`/`last_attempt_at`; both branches clear the lease. A failed send never reverses payment state. If the process crashes during send, the daily job retries the expired `sending` lease; a duplicate email is possible if SES accepted before the crash and must be harmless.

- [ ] **Step 5: Add retry visibility and endpoint**

Return notification status on tenant payout detail and show a `Retry email` action only for `failed`. Add tenant-scoped `POST /api/v1/admin/payouts/{payout_id}/retry-notification`; require payout status `paid` and notification status `failed`, lock the row, change `failed -> pending`, and add one BackgroundTask. Return 404 for another tenant's payout and 409 for any non-retryable notification state. Extend `backend/app/jobs/payout_maintenance.py` to atomically claim `pending` notifications and reset `sending` rows whose lease expired before running the same idempotent delivery function; the daily Fargate task recovers a process crash. Update `backend/deployment/payout-maintenance.yaml` with `EMAIL_BACKEND=ses`, `EMAIL_FROM`, `SES_REGION`, and `FRONTEND_URL`; grant the scheduled task role only `ses:SendEmail` for the verified sender identity. If two request/worker attempts race, only one can claim `sending`. Mark the row `sent` after provider acceptance, not after a claim of inbox delivery.

- [ ] **Step 6: Add authenticated affiliate payout detail and email deep link**

Add affiliate `GET /api/v1/affiliate/payouts/{payout_id}` scoped to the authenticated affiliate plus current `X-Tenant-Id`. Create `PayoutDetailPage`, add route `affiliate/payouts/:id`, link payout table rows to it, and show selected commission lines and `PayoutPayment` reference/date. Include `tenant_id` in the emailed link; it is context only, and the API remains the authorization boundary. Update `AffiliateAuthGuard` to preserve the current internal pathname/query as `returnTo` when redirecting to `/login` or `/merchants`. After login/merchant selection, accept a return path only when it starts with `/affiliate/payouts/` and its `tenant_id` query matches a tenant returned for the authenticated affiliate. Reject external or mismatched return paths and return no payout data until the API verifies affiliate ownership.

- [ ] **Step 7: Run email, API, UI, and build tests**

Run:

```bash
cd backend && TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_email.py tests/test_payout_notification.py tests/test_payout.py -k 'notification or email or payment' -q
cd ../frontend && npm run test -- src/tests/pages/PayoutDetailPage.test.tsx src/tests/components/PayoutsTable.test.tsx && npm run build
```

Expected: email points to the authenticated payout detail; email failure is visible/retryable and the payout remains paid.

- [ ] **Step 8: Commit the notification and affiliate detail flow**

```bash
git add backend/app/api/v1/admin/payouts.py backend/app/api/v1/affiliate/payouts.py backend/app/services/payout.py backend/app/services/email.py backend/app/templates/email/payout_paid.html backend/app/templates/email/payout_paid.txt backend/app/jobs/payout_maintenance.py backend/app/schemas/payout.py backend/tests/test_email.py backend/tests/test_payout_notification.py frontend/src/api/types.ts frontend/src/api/admin/payouts.ts frontend/src/pages/affiliate/PayoutsPage.tsx frontend/src/pages/affiliate/PayoutDetailPage.tsx frontend/src/router.tsx frontend/src/components/admin/PayoutDetail.tsx frontend/src/components/affiliate/PayoutsTable.tsx frontend/src/tests/pages/PayoutDetailPage.test.tsx
git commit -m "Notify affiliates when manual payouts are recorded"
```

## Task 7: Retire legacy payment storage after the service is no longer dependent on it

**Files:**
- Create: `backend/alembic/versions/a1b2c3d4e5f6_retire_incoming_payment_records.py`
- Modify: `backend/app/db/models.py`, `backend/tests/test_document_review_migration.py`, `backend/tests/test_money_models.py`, `backend/tests/test_payout_payment_migration.py`

- [ ] **Step 1: Add failing table-retirement migration tests**

On disposable PostgreSQL databases already at revision `f9a0b1c2d3e4`, seed (a) one legacy `incoming_payment` row or (b) a sale missing `good_date`/external `payment_record_id`; verify upgrading to `head` fails before dropping legacy data. On another database, seed one `affiliate_payout` row, upgrade through `f9a0b1c2d3e4` to verify it is copied one-for-one to `payout_payments`, then upgrade to `head` and verify the old table is removed while the copied row remains. Do not use pytest's ORM `drop_all` fixture for these migration tests.

- [ ] **Step 2: Run the new tests and confirm they fail**

Run from `backend/`:

```bash
uv run pytest tests/test_payout_payment_migration.py -k 'retire or incoming_row' -q
```

Expected before implementation: FAIL because the final retirement migration does not exist.

- [ ] **Step 3: Create revision `a1b2c3d4e5f6` with `down_revision = "f9a0b1c2d3e4"`**

Create `backend/alembic/versions/a1b2c3d4e5f6_retire_incoming_payment_records.py`. This is the contract migration; apply it only after the new App Runner version is fully deployed and old instances are drained. In `upgrade()`, abort if any sale event has null `good_date` or blank/null external `payment_record_id`, if any incoming/unknown `payment_records.record_type` exists, or if any `payouts.paypal_batch_id` value remains. Idempotently copy remaining `affiliate_payout` rows into `payout_payments` using `ON CONFLICT (payout_id) DO NOTHING` and verify every source row matches the target's amount/currency/method/reference/paid time/actor; this catches legacy confirmations from the expand/deploy window. For active payout associations, set `is_active=true` and map legacy linked Commission `pending -> reserved`; recompute non-active due statuses from `available_at`. Verify the partial unique active-link index and allowed Commission/Payout status constraints created in earlier expand revisions. Add `ck_events_sale_payment_context` requiring both sale fields and a nonblank external ID. Then drop `commissions.available_on`, the old payment-record index/table, and `payouts.paypal_batch_id`. In `downgrade()`, abort if any `PayoutPayment`, `PayoutNotification`, Commission, or payout-association rows exist; otherwise restore only empty legacy structures. Do not fabricate or delete transaction history.

- [ ] **Step 4: Remove legacy ORM mappings and keep the sale correlation ID**

After the retirement revision exists, remove `PaymentRecord`, `Payout.payment_record`, `Payout.paypal_batch_id`, and legacy `Commission.available_on` from `backend/app/db/models.py`; retain `Event.payment_record_id` as a string. Update `backend/tests/test_document_review_migration.py` so the current head is `a1b2c3d4e5f6` with parent `f9a0b1c2d3e4`.

In `backend/tests/test_money_models.py`, assert `"payment_records" not in Base.metadata.tables`, `PayoutPayment.__tablename__ == "payout_payments"`, and `Event.__table__.c.payment_record_id` still exists. Include `PayoutPayment.amount` in the `NUMERIC(20,2)` assertions; no test imports the deleted `PaymentRecord` model. Historical Alembic revisions continue to mention `payment_records` so fresh databases can upgrade through the old schema.

- [ ] **Step 5: Verify both migration outcomes on separate disposable databases**

First upgrade the incoming-free database through all revisions. On a second database, upgrade only to `f9a0b1c2d3e4`, insert an incoming row, then attempt the final revision:

```bash
DATABASE_URL="$PAYOUT_MIGRATION_TEST_DATABASE_URL" uv run alembic upgrade head
DATABASE_URL="$PAYOUT_INCOMING_ROW_TEST_DATABASE_URL" uv run alembic upgrade f9a0b1c2d3e4
DATABASE_URL="$PAYOUT_INCOMING_ROW_TEST_DATABASE_URL" uv run alembic upgrade head
```

Expected: first DB reaches `a1b2c3d4e5f6` with every payout-linked amount, currency, method, reference, paid time, and user ID preserved. The second stays at `f9a0b1c2d3e4`; the final upgrade aborts and the incoming table/row remain intact for the owner-approved retention decision.

- [ ] **Step 6: Run migration and money-model tests**

Run from `backend/`:

```bash
uv run pytest tests/test_document_review_migration.py tests/test_payout_payment_migration.py tests/test_money_models.py -q
```

Expected: PASS; the revision graph ends at `a1b2c3d4e5f6`, the ORM no longer maps incoming payment records, and payout money precision remains `NUMERIC(20,2)`.

- [ ] **Step 7: Commit the legacy table retirement**

```bash
git add backend/alembic/versions/a1b2c3d4e5f6_retire_incoming_payment_records.py backend/app/db/models.py backend/tests/test_document_review_migration.py backend/tests/test_money_models.py backend/tests/test_payout_payment_migration.py
git commit -m "Retire incoming payment-record storage safely"
```

## Task 8: Product-level verification and release gate

**Files:**
- Verify: all files listed above; update `docs/workflows/REGISTRY.md`, `WORKFLOW-merchant-payout-settlement.md`, and Workstream 0.6 in `docs/superpowers/plans/2026-09-30-affiliate-service-next-phase-execution-plan.md` after implementation passes.

- [ ] **Step 1: Run all focused payout and migration checks**

Run from `backend/`:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_payout.py tests/test_payout_notification.py tests/test_email.py tests/test_dashboard.py tests/test_events.py tests/test_document_review_migration.py tests/test_payout_payment_migration.py -v
```

Expected: PASS; tests use a disposable database and migration tests use separate migration databases.

- [ ] **Step 2: Run the complete repo verification**

Run from `frontend/` and `backend/`:

```bash
cd backend && TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/ -v
cd ../frontend && npm run test && npm run build && npm run lint
```

Expected: PASS. Run E2E only with the documented local backend and test tenant; do not run payment tests against live PayPal or production data.

- [ ] **Step 3: Validate the deployed Fargate job and App Runner routes**

In the configured non-production AWS environment, deploy the maintenance stack and verify: one `cron(15 0 * * ? *)` UTC invocation promotes due rows; stopped nonzero ECS tasks are visible in CloudWatch; an invalid DB secret/network causes a failed run without marking commissions available; the next successful run catches up.

- [ ] **Step 4: Reconcile documentation and release gate**

Mark W0.6 acceptance items complete only after tests, disposable migration conversion, and non-production scheduled-job verification pass. Update the workflow registry and workflow `Reality review findings`; do not mark a workflow `Approved` until implementation matches the documented branches.

## Acceptance gate

- Pending commissions become available on the next successful daily job when `available_at <= now_utc`; retries and missed runs catch up without duplicate changes.
- Merchants can inspect every commission before approve/reject; rejection releases all selected commissions exactly once and retains the old association.
- Only approved payouts can be confirmed paid, and confirmation stores merchant-entered `paid_at` plus PayPal reference in exactly one `PayoutPayment`.
- Payment commit, commission-paid transitions, and notification creation are atomic. Email failure never reverts a paid payout and has a visible retry path.
- Incoming payment-record ingestion/storage is retired only after outgoing rows have been migrated and the incoming-row retention preflight passes; `Event.payment_record_id` remains intact.
- No PayPal API credentials/client, batch dispatch, or automatic payout path remains in the active product configuration; stale SQS payout messages remain harmless no-ops during retirement.
- Affiliate payout detail/history and merchant paid payout summaries reconcile to source rows by currency and date.
