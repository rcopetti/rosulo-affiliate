# Commission Availability and Affiliate Payout Request Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mature commissions from the merchant-provided `good_date` and let an eligible affiliate request payment for all or selected whole available commissions without entering an amount.

**Architecture:** Sale events require a date-only `good_date`, interpreted as 00:00 UTC and stored on commissions as `available_at`. An idempotent service promotes due commissions, invoked by a once-daily EventBridge Scheduler ECS/Fargate task using the repository's existing one-shot Fargate deployment pattern. Payout requests lock and validate whole commission rows, derive totals, and reserve them atomically with an active payout association.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 async, PostgreSQL, Alembic, AWS ECS/Fargate, EventBridge Scheduler, React, TypeScript, TanStack Query, pytest, Vitest.

---

## Prerequisites and safety gates

- Workstream W0.2 must be committed and present as the current code/migration baseline. The verified current Alembic head is `b1c2d3e4f5a6` (`uv run --no-sync alembic history`); the new migration in this plan uses that as `down_revision`.
- Preserve any unrelated staged work. Before coding, inspect `git status --short --branch`; do not stage or commit unrelated W0.2/user changes with this plan.
- `backend/tests/conftest.py` drops and recreates its configured database. Set `TEST_DATABASE_URL` only to a disposable PostgreSQL database before running pytest.
- Before migration verification, provision a separate disposable PostgreSQL database and set `PAYOUT_MIGRATION_TEST_DATABASE_URL`. Never run upgrade/downgrade tests against a data-retaining or production database.
- Production currently runs the API in AWS App Runner and runs migrations as one-shot ECS/Fargate tasks (`backend/run-migration.sh`). Use an ECS scheduled task rather than an in-process App Runner timer, so API replica count/restarts cannot determine whether maturity runs.
- Migration `e8f9a0b1c2d3` is an expand-only migration: retain `available_on` and legacy payout/payment mappings during the App Runner rollout. Plan 2's final contract migration drops them only after the new app version is fully deployed and old instances are drained. Do not perform payout mutations during the scheduled schema/app rollout window.

## File map

| File | Responsibility in this plan |
|---|---|
| `backend/app/schemas/event.py` | Require `good_date` for sale events while allowing it to be absent on clicks/leads |
| `backend/app/db/models.py` | Store commission `available_at`; represent an active payout-commission association explicitly |
| `backend/app/schemas/commission.py` | Expose `available_at` and `reserved` status |
| `backend/app/services/commission.py` | Create commission due instants and promote due pending rows idempotently |
| `backend/app/services/balance.py`, `backend/app/services/dashboard.py`, `backend/app/schemas/dashboard.py` | Add reserved balance bucket and include reserved rows in merchant commission liability |
| `backend/app/jobs/__init__.py`, `backend/app/jobs/payout_maintenance.py` | Run the one-shot scheduled maintenance command |
| `backend/deployment/payout-maintenance.yaml` | Declare the UTC EventBridge Scheduler ECS/Fargate task, role, network, retry/DLQ, and logs |
| `backend/alembic/versions/e8f9a0b1c2d3_commission_availability_and_reservations.py` | Migrate due instants and commission reservation history from the current head |
| `backend/app/schemas/payout.py`, `backend/app/services/payout.py` | Validate all/selected commission IDs and derive payout totals from locked rows |
| `backend/app/api/v1/affiliate/payouts.py`, `backend/app/api/v1/affiliate/balance.py`, `backend/app/api/v1/public/events.py` | Expose commission-backed requests and stop request-time/lazy maturity |
| `frontend/src/api/types.ts`, `frontend/src/api/affiliate/commissions.ts`, `frontend/src/api/affiliate/payouts.ts` | Share due-date/status/selection DTOs with the UI |
| `frontend/src/pages/affiliate/RequestPayoutPage.tsx`, `frontend/src/components/affiliate/CommissionsTable.tsx`, `frontend/src/components/affiliate/StatsCards.tsx`, `frontend/src/components/affiliate/CurrencyBalances.tsx` | Select whole available commissions and show the reserved balance bucket; never accept a payout amount |
| `backend/tests/conftest.py`, `backend/tests/test_events.py`, `backend/tests/test_commission.py`, `backend/tests/test_payout.py`, `backend/tests/test_balance.py`, `backend/tests/test_dashboard.py`, `backend/tests/test_tracking.py`, `backend/tests/test_document_review_migration.py` | Shared payout scenario fixture; verify required sale fields, due processing, reservations, currency buckets, and Alembic chain |
| `backend/tests/test_commission_availability.py` | Focused scheduled-maturity service/job tests |
| `frontend/src/tests/pages/RequestPayoutPage.test.tsx`, `frontend/src/tests/components/CommissionsTable.test.tsx`, `frontend/src/tests/components/CurrencyBalances.test.tsx` | Verify available-item selection, server-derived totals, and reserved balance display |

## Task 1: Require merchant `good_date` and external payment ID on every sale event

**Files:**
- Modify: `backend/app/schemas/event.py`
- Test: `backend/tests/test_events.py`, `backend/tests/test_commission.py`, `backend/tests/test_payout.py`, `backend/tests/test_dashboard.py`, `backend/tests/test_tracking.py`

- [ ] **Step 1: Add the failing schema test**

```python
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.event import EventCreate


def test_sale_event_requires_good_date():
    with pytest.raises(ValidationError, match="good_date is required for sale events"):
        EventCreate(event_id="sale-without-date", type="sale", payment_record_id="pay-1")


def test_sale_event_requires_payment_record_id():
    with pytest.raises(ValidationError, match="payment_record_id is required for sale events"):
        EventCreate(event_id="sale-without-payment-id", type="sale", good_date=date(2026, 10, 1))


def test_click_event_does_not_require_good_date():
    event = EventCreate(event_id="click-without-date", type="click")
    assert event.good_date is None
```

- [ ] **Step 2: Run the test and confirm the sale case fails**

Run from `backend/`:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_events.py -k 'requires_good_date or requires_payment_record_id' -q
```

Expected before implementation: FAIL because `EventCreate` accepts a sale missing either required value.

- [ ] **Step 3: Add conditional Pydantic validation**

In `backend/app/schemas/event.py`, import `model_validator` and add this validator to `EventCreate`:

```python
    @model_validator(mode="after")
    def sale_requires_good_date_and_payment_record_id(self):
        if self.type == "sale":
            if self.good_date is None:
                raise ValueError("good_date is required for sale events")
            if not self.payment_record_id or not self.payment_record_id.strip():
                raise ValueError("payment_record_id is required for sale events")
        return self
```

Keep `good_date: date | None = None` and `payment_record_id: str | None = None` at the field level so click/lead events do not need them; the sale model validator requires both for `type="sale"` and rejects a blank ID. Do not derive a date from `occurred_at`, `date.today()`, or an incoming payment record.

- [ ] **Step 4: Verify the event contract and persistence behavior**

Update every sale-event test fixture in `test_events.py`, `test_commission.py`, `test_payout.py`, `test_dashboard.py`, and `test_tracking.py` with a unique external `payment_record_id`; keep clicks/leads without these sale-only fields. Run from `backend/`:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_events.py tests/test_commission.py tests/test_payout.py tests/test_dashboard.py tests/test_tracking.py -q
```

Expected: PASS; a sale missing either `good_date` or `payment_record_id` returns 422 and creates no Event or Commission, while click/lead payloads may omit both fields.

- [ ] **Step 5: Commit the event contract change**

```bash
git add backend/app/schemas/event.py backend/tests/test_events.py backend/tests/test_commission.py backend/tests/test_payout.py backend/tests/test_dashboard.py backend/tests/test_tracking.py
git commit -m "Require merchant due dates and payment IDs on sales"
```

## Task 2: Migrate commission due time and active payout reservation state

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/alembic/versions/e8f9a0b1c2d3_commission_availability_and_reservations.py`
- Modify: `backend/tests/test_document_review_migration.py`
- Create: `backend/tests/test_commission_availability_migration.py`

- [ ] **Step 1: Add the failing migration-chain assertion**

Add a test to `backend/tests/test_document_review_migration.py`:

```python
def test_commission_availability_migration_follows_manual_payout_head():
    backend_dir = Path(__file__).resolve().parents[1]
    config = Config(str(backend_dir / "alembic.ini"))
    script = ScriptDirectory.from_config(config)

    assert script.get_current_head() == "e8f9a0b1c2d3"
    assert script.get_revision("e8f9a0b1c2d3").down_revision == "b1c2d3e4f5a6"
```

- [ ] **Step 2: Run the chain test and confirm it fails**

Run from `backend/`:

```bash
uv run pytest tests/test_document_review_migration.py::test_commission_availability_migration_follows_manual_payout_head -q
```

Expected before implementation: FAIL because revision `e8f9a0b1c2d3` does not exist.

- [ ] **Step 3: Define the ORM fields and state contract**

In `backend/app/db/models.py`:

- Add nullable `Commission.available_at: DateTime(timezone=True)` while retaining legacy `Commission.available_on: Date` through the App Runner rolling deployment. New code writes both fields from `good_date`; the final contract migration in Plan 2 removes `available_on` after old app versions have drained.
- Add `PayoutCommission.is_active: Boolean`, non-null, default false. Historical rows remain; true marks a new-code active reservation. Compatibility queries also treat any link to a `pending_approval`/`approved` payout as active because older app instances do not know this column.
- Keep `Commission.status` values `pending`, `available`, `reserved`, `paid`, and `reversed` consistent with `docs/superpowers/specs/2026-10-01-commission-backed-manual-payouts-design.md`. Do not rewrite legacy active-payout commissions from `pending` to `reserved` until Plan 2's final contract migration after App Runner rollout.

- [ ] **Step 4: Create revision `e8f9a0b1c2d3` with fail-closed migration checks**

Create `backend/alembic/versions/e8f9a0b1c2d3_commission_availability_and_reservations.py` with `down_revision = "b1c2d3e4f5a6"`. In `upgrade()`:

1. Abort with a clear `RuntimeError` if any existing sale event has null `good_date` or null/blank `payment_record_id`; do not use `occurred_at` as a fallback or invent an external payment ID.
2. Abort if any payout status is outside `pending_approval`, `approved`, `rejected`, or `paid`; reconcile legacy `requested`, `processing`, or `failed` rows before retrying.
3. Abort if any commission status is outside `pending`, `available`, `paid`, or `reversed`, or if one commission is linked to more than one `pending_approval`/`approved` payout.
4. Add nullable `commissions.available_at TIMESTAMPTZ`; populate it from `events.good_date::timestamp AT TIME ZONE 'UTC'`. Keep it nullable for non-sale reversal rows and retain `available_on`; do not drop or repurpose the legacy column in this expand migration.
5. Add `payout_commissions.is_active BOOLEAN NOT NULL DEFAULT FALSE`; set it true for existing links to `pending_approval` or `approved` payouts. Old App Runner code inserts with the false default, so runtime maturity/validation must also check parent payout status.
6. Do not rewrite existing active `Commission.status` values. New code presents a pending commission linked to a pending/approved payout as logically `reserved`; Plan 2's final contract migration maps stored statuses after old App Runner versions have drained.
7. Add `ck_commissions_status` permitting `pending`, `available`, `reserved`, `paid`, and `reversed`, plus a partial unique index on `payout_commissions(commission_id)` where `is_active IS TRUE`. Keep `available_on` for old App Runner code; Plan 2's final contract migration drops it after rollout.

In `downgrade()`, abort if any commission or payout-commission association exists: the added due timestamps cannot be translated back to the old 14-day policy. Only when both tables contain no rows may downgrade remove `available_at`/`is_active` and retain the unchanged `available_on` column.

- [ ] **Step 5: Add migration preflight coverage**

In `backend/tests/test_commission_availability_migration.py`, test that the revision's preflight SQL detects a sale commission with a missing `good_date`, missing external `payment_record_id`, and duplicate active commission links. Keep these tests isolated from the ORM-created pytest schema; use the disposable PostgreSQL migration smoke check in Task 8 for actual DDL/data conversion.

- [ ] **Step 6: Verify the model and revision chain**

Run from `backend/`:

```bash
uv run pytest tests/test_document_review_migration.py tests/test_commission_availability_migration.py -q
```

Expected: PASS; the current Alembic head is `e8f9a0b1c2d3`, `Commission.available_at` is timezone-aware, and only one association can be active per commission.

- [ ] **Step 7: Commit the schema change**

```bash
git add backend/app/db/models.py backend/alembic/versions/e8f9a0b1c2d3_commission_availability_and_reservations.py backend/tests/test_document_review_migration.py backend/tests/test_commission_availability_migration.py
git commit -m "Use merchant due dates for commission availability"
```

## Task 3: Implement idempotent due-commission promotion

**Files:**
- Modify: `backend/app/services/commission.py`, `backend/app/api/v1/public/events.py`
- Modify: `backend/tests/conftest.py`, `backend/tests/test_commission.py`
- Create: `backend/tests/test_commission_availability.py`

- [ ] **Step 1: Add due/not-due and repeated-run tests**

First add a `payout_scenario` fixture to `backend/tests/conftest.py` by extracting the existing tenant login, invitation, affiliate acceptance, campaign creation, and commission setup from `backend/tests/test_payout.py::test_payout_flow`. The fixture returns `create_commission(good_date, payment_record_id)`, `commission_status(commission_id)`, `add_legacy_active_payout(commission_id)`, and an async DB-session context; use the existing autouse DB reset and never add live payment webhooks. Then add due/not-due, legacy-active-reservation, and repeated-run tests in `backend/tests/test_commission_availability.py`. Fix the clock by passing `now_utc`, not by sleeping or depending on the machine date.

```python
@pytest.mark.asyncio
async def test_maturity_promotes_only_due_pending_commissions(payout_scenario):
    due_id = await payout_scenario.create_commission(date(2026, 10, 1), "payment-due-1")
    future_id = await payout_scenario.create_commission(date(2026, 10, 2), "payment-future-1")

    async with payout_scenario.db_session() as db:
        promoted = await mature_due_commissions(
            db,
            now_utc=datetime(2026, 10, 1, 0, 15, tzinfo=timezone.utc),
        )

    assert promoted == 1
    assert await payout_scenario.commission_status(due_id) == "available"
    assert await payout_scenario.commission_status(future_id) == "pending"
```

Add a test that a due legacy commission with `status="pending"` linked to a `pending_approval` or `approved` payout is not promoted even when its legacy `PayoutCommission.is_active` default is false. Add a repeated-run test that expects the second invocation to promote zero rows and leave statuses unchanged.

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run from `backend/`:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_commission_availability.py -q
```

Expected before implementation: FAIL because `mature_due_commissions` is not implemented; the `payout_scenario` fixture is added in this step and should resolve.

- [ ] **Step 3: Implement the maturity service**

Replace the affiliate-scoped, date-only `mark_available_commissions` helper in `backend/app/services/commission.py` with `mature_due_commissions(db, now_utc=None)`. It must select due `pending` rows joined to their source Event, lock rows in deterministic order with `FOR UPDATE SKIP LOCKED`, and exclude any commission linked to a Payout whose status is `pending_approval` or `approved` (check parent payout status as well as `is_active` to cover old app inserts). If an older App Runner instance created a commission after the expand migration and left `available_at` null, derive UTC midnight from `Event.good_date`; mirror `Event.good_date` into legacy `available_on`. Promote only when the derived/stored instant is `<= now_utc`; commit the batch and return the number promoted. Do not update `reserved`, `paid`, or `reversed` commissions. Repeated or overlapping jobs are safe because rows are locked and the update is conditional on `status == pending`.

- [ ] **Step 4: Set `available_at` from `good_date` when calculating a commission**

In `calculate_from_sale_event`, derive `available_at` as midnight UTC for `event.good_date` and set legacy `available_on=event.good_date` during the rolling-deployment window. Because Task 1 guarantees both sale fields, remove the `good_date or today` fallback and the `timedelta(days=14)` addition. New rows start as `pending`; only the scheduled process promotes them. In `backend/app/api/v1/public/events.py`, remove the call to the old `mark_available_commissions` helper so sale-event ingestion never bypasses the daily job.

- [ ] **Step 5: Verify maturity, currency, and commission regressions**

Run from `backend/`:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_commission_availability.py tests/test_commission.py tests/test_events.py -q
```

Expected: PASS; due dates are exact UTC midnights, future rows stay pending, and repeated runs do not change a row twice.

- [ ] **Step 6: Commit the maturity service**

```bash
git add backend/app/services/commission.py backend/tests/test_commission.py backend/tests/test_commission_availability.py
git commit -m "Promote commissions when merchant due dates arrive"
```

## Task 4: Add the one-shot scheduled job and AWS schedule

**Files:**
- Create: `backend/app/jobs/__init__.py`
- Create: `backend/app/jobs/payout_maintenance.py`
- Create: `backend/deployment/payout-maintenance.yaml`
- Test: `backend/tests/test_payout_maintenance_job.py`

- [ ] **Step 1: Add a job test for summary and failure exit behavior**

Test the async `run_maturity_job(db_factory)` function with a fake service result and a service exception. Success returns/logs `{promoted_count: 3}`; failure propagates so the ECS task exits non-zero and is visible to EventBridge/CloudWatch. The job must not call FastAPI request handlers or create a second scheduler inside App Runner.

- [ ] **Step 2: Implement the executable one-shot command**

Create `backend/app/jobs/payout_maintenance.py` with an async function that opens one `async_session()`, calls `mature_due_commissions`, logs a generated run ID plus UTC start/end and promoted count, and closes the session. Wrap the database operation in `asyncio.timeout(600)`; cancellation must roll back the open SQLAlchemy transaction and exit nonzero. Add a `main()` wrapper using `asyncio.run(main_async())`, so the container command is `python -m app.jobs.payout_maintenance`.

- [ ] **Step 3: Add the EventBridge Scheduler ECS/Fargate deployment template**

Create `backend/deployment/payout-maintenance.yaml` using CloudFormation resources for:

- An `AWS::ECS::TaskDefinition` with `FARGATE`, `awsvpc`, 256 CPU/512 MiB minimum, an image URI parameter, container command `python -m app.jobs.payout_maintenance`, `awslogs` driver, and `DATABASE_URL` injected from an SSM Parameter Store ARN through the ECS `Secrets` field.
- An EventBridge Scheduler schedule `cron(15 0 * * ? *)` with `ScheduleExpressionTimezone: UTC` and flexible window disabled.
- An ECS `RunTask` target in the existing `allbum-cluster-serverless` cluster, using Fargate, `awsvpc`, the production subnets/security group, and the task definition above.
- A scheduler execution role scoped to `ecs:RunTask` on the maintenance task definition and `iam:PassRole` only for its task/execution roles.
- A Scheduler DLQ and retry policy (2 delivery retries, one-hour event age) plus ECS/CloudWatch task logs. A task that starts but exits non-zero must be visible in ECS stopped-task logs; a subsequent daily run catches up.
- Parameters for image URI, cluster ARN, subnets, security group, ECS task/execution role ARNs, database SSM parameter ARN, and log retention. Never put credentials in the template, schedule payload, or command line.

Use `backend/run-migration.sh` and `backend/docker/entrypoint.sh` as repository deployment patterns. Do not add a scheduler process to the App Runner web-server lifespan: App Runner can run multiple replicas and restart independently.

- [ ] **Step 4: Validate the schedule template and job command**

Run from repository root:

```bash
aws cloudformation validate-template --template-body file://backend/deployment/payout-maintenance.yaml
cd backend && uv run pytest tests/test_payout_maintenance_job.py tests/test_commission_availability.py -q
```

Expected: CloudFormation validation reports a valid template; focused tests pass without contacting AWS. A deployment smoke run is performed only in the configured AWS account after the task role, SSM parameter, network, and DLQ are reviewed.

- [ ] **Step 5: Commit the scheduled job**

```bash
git add backend/app/jobs/__init__.py backend/app/jobs/payout_maintenance.py backend/deployment/payout-maintenance.yaml backend/tests/test_payout_maintenance_job.py
git commit -m "Schedule commission maturity on Fargate"
```

## Task 5: Accept selected commission IDs and reserve atomically

**Files:**
- Modify: `backend/app/schemas/payout.py`, `backend/app/schemas/dashboard.py`
- Modify: `backend/app/services/payout.py`, `backend/app/services/balance.py`, `backend/app/services/dashboard.py`
- Modify: `backend/app/api/v1/affiliate/payouts.py`
- Modify: `backend/tests/test_payout.py`, `backend/tests/test_balance.py`, `backend/tests/test_dashboard.py`

- [ ] **Step 1: Add request-validation tests**

Test `PayoutRequest` rejects empty `commission_ids`, duplicate IDs, malformed UUIDs, and extra `amount`; omitting IDs remains the “all available in this currency” request.

```python
def test_payout_request_rejects_empty_commission_ids():
    with pytest.raises(ValidationError):
        PayoutRequest(currency="USD", commission_ids=[])


def test_payout_request_rejects_client_amount():
    with pytest.raises(ValidationError):
        PayoutRequest(currency="USD", amount=1)
```

- [ ] **Step 2: Run the request-schema tests and confirm they fail**

Run from `backend/`:

```bash
uv run pytest tests/test_payout.py -k 'commission_ids or client_amount' -q
```

Expected before implementation: FAIL because `PayoutRequest` has no ID list and ignores extra fields.

- [ ] **Step 3: Add strict all-or-selected request schema**

In `backend/app/schemas/payout.py`, import `ConfigDict` and `uuid` as needed, then implement the request schema as:

```python
class PayoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field(..., pattern="^[A-Za-z]{3}$")
    commission_ids: list[uuid.UUID] | None = None

    @field_validator("commission_ids")
    @classmethod
    def validate_commission_ids(cls, value: list[uuid.UUID] | None) -> list[uuid.UUID] | None:
        if value is not None and (not value or len(value) != len(set(value))):
            raise ValueError("commission_ids must contain unique commission IDs")
        return value
```

Omitting IDs means all available rows in that currency. Do not add an amount field.

- [ ] **Step 4: Add all/selected service tests**

Using `payout_scenario`, test omitted IDs reserves all available commissions in that currency; a subset reserves only those IDs; a foreign affiliate ID, wrong currency, stale status, or unavailable commission rejects the whole request without partial payout creation. Assert payout gross/withholding/net equals the exact selected commission sums. In `backend/tests/test_balance.py`, add a reserved commission and assert it is reported only in the `reserved` bucket, not `available` or `pending`; assert `get_balances` does not promote due rows. In `backend/tests/test_dashboard.py`, assert reserved commissions remain in merchant liability.

- [ ] **Step 5: Implement locked validation and atomic reservation**

Change `request_payout(db, affiliate, currency, commission_ids=None)` to:

1. Validate payout eligibility and supported currency.
2. Query all available rows in that affiliate/currency when IDs are omitted; otherwise query the exact IDs scoped to affiliate and currency.
3. Lock rows in sorted ID order with `FOR UPDATE`; compare result count with submitted distinct IDs; return 409 if any selected item is no longer available, is outside the affiliate/tenant, or has another currency.
4. Derive amounts from those rows; create `Payout(status="pending_approval")` and links with `PayoutCommission.is_active=True`; change commission status `available -> reserved`; append the initial transition; commit once.
5. Convert an active-link partial-unique violation into 409 after rolling back. Do not call the old lazy `mark_available_commissions` from payout creation.

Update `backend/app/services/balance.py` to remove its lazy maturity call and calculate a logical status with SQL `CASE`: a stored `pending` commission with any linked payout in `pending_approval` or `approved` is exposed as `reserved`; otherwise expose the stored status. Add `reserved` to every currency bucket and the single-currency/empty legacy response, separate from `available`. Use the same logical status in the affiliate commission-list endpoint. Add `reserved` to `CurrencyBalanceOut`/`BalanceOut` in `backend/app/schemas/dashboard.py`, and include it in `backend/app/services/dashboard.py` commission liability alongside pending and available.

Update `reject_payout`: verify each linked commission is `reserved` or is a legacy `pending` commission linked to this active payout; set each association `is_active=False`, restore the commission to `available`, and set payout `rejected` in the same transaction. Keep the association row for history.

- [ ] **Step 6: Verify concurrent selections and rejection reuse**

Run from `backend/`:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_payout.py tests/test_balance.py tests/test_dashboard.py -k 'request or reject or concurrent or reserved' -q
```

Expected: PASS; two requests for the same commission cannot both succeed, rejection releases it once, and a later payout can create a second inactive/historical association.

- [ ] **Step 7: Commit the API/service contract**

```bash
git add backend/app/schemas/payout.py backend/app/schemas/dashboard.py backend/app/services/payout.py backend/app/services/balance.py backend/app/services/dashboard.py backend/app/api/v1/affiliate/payouts.py backend/tests/test_payout.py backend/tests/test_balance.py backend/tests/test_dashboard.py
git commit -m "Reserve selected commission batches atomically"
```

## Task 6: Build affiliate whole-commission selection UI

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/affiliate/commissions.ts`, `frontend/src/api/affiliate/payouts.ts`
- Modify: `frontend/src/components/affiliate/CommissionsTable.tsx`
- Modify: `frontend/src/pages/affiliate/RequestPayoutPage.tsx`
- Modify: `frontend/src/tests/pages/RequestPayoutPage.test.tsx`
- Create: `frontend/src/tests/components/CommissionsTable.test.tsx`

- [ ] **Step 1: Add failing UI tests for all vs. selected commissions**

Mock `getCommissions`, render the payout request page, choose a currency, select one of two available whole commissions, and assert the request API receives `{currency: "USD", commission_ids: [selectedId]}`. Add a second test for “all available” that omits `commission_ids`. Assert pending/reserved/paid/reversed commissions are not selectable and no amount input is rendered.

- [ ] **Step 2: Run the focused test and confirm it fails**

Run from `frontend/`:

```bash
npm run test -- src/tests/pages/RequestPayoutPage.test.tsx
```

Expected before implementation: FAIL because the UI requests by currency only and displays a balance total instead of commission rows.

- [ ] **Step 3: Update TypeScript contracts**

Change `Commission.status` to `'pending' | 'available' | 'reserved' | 'paid' | 'reversed'`; rename `available_on` to `available_at`; add `reserved: number` to `CurrencyBalance` and the legacy `Balance` response; add typed request payload `{currency: string; commission_ids?: string[]}` and update `requestPayout` to post that object. Keep totals numeric and server-derived.

- [ ] **Step 4: Load and show only eligible rows for the selected currency**

Use existing `getCommissions()` from `frontend/src/api/affiliate/commissions.ts`; filter to `status === 'available'` and the selected currency. Add “All available” and “Selected commissions” modes, a selectable row for each eligible whole commission, and a confirmation summary showing commission count, gross, withholding, and net. Client totals are preview only; the server response remains authoritative. Do not add a free-form amount input. Update `StatsCards` to display the new reserved balance bucket and `CurrencyBalances` empty-state defaults so amounts remain visible per currency.

- [ ] **Step 5: Update status rendering and request submission**

Add the `reserved` variant to `CommissionsTable` status mapping. Show reserved balances separately in `StatsCards`, include them in `CurrencyBalances` fallback objects, and update `CurrencyBalances.test.tsx` fixtures to assert they are displayed without being added to available. Disable submission when no whole commissions are selected in selected mode or when payout eligibility is false. On success, invalidate balance, commission, and payout queries and navigate to payout history.

- [ ] **Step 6: Run focused frontend tests and build**

Run from `frontend/`:

```bash
npm run test -- src/tests/pages/RequestPayoutPage.test.tsx src/tests/components/CommissionsTable.test.tsx src/tests/components/CurrencyBalances.test.tsx
npm run build
```

Expected: focused tests PASS and TypeScript/Vite build completes without errors.

- [ ] **Step 7: Commit the affiliate selection UI**

```bash
git add src/api/types.ts src/api/affiliate/commissions.ts src/api/affiliate/payouts.ts src/components/affiliate/CommissionsTable.tsx src/components/affiliate/StatsCards.tsx src/components/affiliate/CurrencyBalances.tsx src/pages/affiliate/RequestPayoutPage.tsx src/tests/pages/RequestPayoutPage.test.tsx src/tests/components/CommissionsTable.test.tsx src/tests/components/CurrencyBalances.test.tsx
git commit -m "Let affiliates select payable commission batches"
```

## Task 7: Verify the complete stage and migration safety

**Files:**
- Test: `backend/tests/test_events.py`, `backend/tests/test_commission.py`, `backend/tests/test_payout.py`, `frontend/src/tests/pages/RequestPayoutPage.test.tsx`
- Verify: `backend/alembic/versions/e8f9a0b1c2d3_commission_availability_and_reservations.py`

- [ ] **Step 1: Run backend focused and full tests on a disposable test database**

Run from `backend/`:

```bash
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/test_events.py tests/test_commission.py tests/test_commission_availability.py tests/test_balance.py tests/test_dashboard.py tests/test_payout.py -v
TEST_DATABASE_URL="$TEST_DATABASE_URL" uv run pytest tests/ -v
```

Expected: both commands PASS; `TEST_DATABASE_URL` must point to a disposable database because `conftest.py` drops/recreates its tables.

- [ ] **Step 2: Upgrade a separate disposable database through the new revision**

Run from `backend/` after verifying the database name and contents are disposable:

```bash
DATABASE_URL="$PAYOUT_MIGRATION_TEST_DATABASE_URL" uv run alembic upgrade head
DATABASE_URL="$PAYOUT_MIGRATION_TEST_DATABASE_URL" uv run alembic current
```

Expected: current revision is `e8f9a0b1c2d3`; migration preflights fail before destructive DDL for a fixture with missing sale `good_date` or duplicate active reservations.

- [ ] **Step 3: Run frontend tests and static checks**

Run from `frontend/`:

```bash
npm run test
npm run build
npm run lint
```

Expected: all tests/build/lint pass.

- [ ] **Step 4: Review the resulting changes and commit test-only fixes**

Run from repository root:

```bash
git diff --check
git status --short --branch
```

Expected: no whitespace errors; no unrelated staged changes are included in this plan's commits.

## Acceptance gate

- Every sale event requires merchant `good_date` and external `payment_record_id`; `good_date` is interpreted as 00:00 UTC without adding 14 days.
- Due pending commissions are promoted by the once-daily ECS job; repeated runs and failed/missed runs are safe and catch up.
- Affiliates can request all commissions in a currency or a selected set of whole commission IDs; no amount is accepted.
- Totals are derived from selected commission rows; mixed currencies and partial requests are rejected atomically.
- A commission has at most one active payout association; rejected associations remain historical and released commissions can be requested again.
- Reserved commissions appear in a separate per-currency balance bucket and in merchant liability; they are never included in the affiliate's available balance.
- W0.2 transition/payment behavior remains intact and is verified against the new `reserved` status.
