# WORKFLOW: Commission Maturity

**Version**: 1.0
**Date**: 2026-10-01
**Author**: Workflow design
**Status**: Implemented
**Implements**: Commission-backed manual payout product design

## Overview

A merchant sends a sale event after customer payment is confirmed and supplies the merchant-defined `good_date`. Rosulo calculates an eligible commission as `pending`, then a daily UTC process promotes it when the date-derived `available_at` is due. Rosulo does not add a 14-day hold and does not rely on an affiliate opening the payout page to make a commission available.

## Actors

| Actor | Role |
|---|---|
| Merchant integration | Sends idempotent sale events and chooses `good_date` |
| Event API | Validates and persists the sale event |
| Commission service | Calculates the commission and its due instant |
| Daily scheduler | Starts the due-commission process at least once per UTC day |
| Database | Stores events, commissions, and status changes |

## Prerequisites

- The merchant API key is valid and scoped to the event's tenant.
- The event is a valid, idempotent sale attributed to a campaign/affiliate.
- The sale event includes required `good_date` and external `payment_record_id`; `good_date` is the due date, not a date to which Rosulo adds a hold.
- Contract and currency rules permit a payable commission. An unsupported currency or no applicable commission term produces no payable commission.
- Deploy `backend/deployment/payout-maintenance.yaml`, which configures EventBridge Scheduler to start a one-shot ECS/Fargate task at 00:15 UTC daily. The schedule is planned but not yet deployed.

## Trigger

1. Merchant submits `POST /api/v1/events` with `type=sale` after payment confirmation.
2. EventBridge Scheduler launches the ECS/Fargate maintenance task daily at 00:15 UTC.

## Workflow tree

### STEP 1: Validate and persist sale

**Actor**: Event API
**Action**: Validate tenant authentication, idempotency, attribution, required `good_date`, and nonblank external `payment_record_id`; persist the event. The external ID is retained for future refund correlation and is not checked against a Rosulo incoming-payment table.
**Timeout**: HTTP request timeout configured by the API runtime.
**Input**: Sale event including `event_id`, `amount`, `currency`, `payment_sequence`, `good_date`, and external `payment_record_id`.
**Output on SUCCESS**: Persisted event -> STEP 2.
**Output on FAILURE**:
- `FAILURE(validation_error)`: Missing/invalid `good_date`, blank/missing `payment_record_id`, attribution, or payload -> return validation error; do not create an event or commission.
- `SUCCESS(duplicate_with_commission)`: Same tenant/event ID and a commission already exists -> return the original event and commission result; do not create a second commission.
- `SUCCESS(duplicate_without_commission)`: Same tenant/event ID exists but no commission row exists -> continue to STEP 2 to resume commission generation idempotently.
- `FAILURE(timeout_or_database)`: If event persistence did not commit, caller retries with the same `event_id`; if the event committed but commission calculation did not, the same retry resumes STEP 2. Never duplicate the event or commission.

**Observable states**:
- Merchant integration sees accepted event or actionable validation error.
- Operator sees event or validation log scoped to tenant/event ID.
- Database may contain a committed event with no commission if the separate commission transaction fails; an idempotent event retry resumes calculation. Uncommitted event writes are absent.
- Logs contain tenant ID, event ID, result code, and trace ID; never log API keys.

### STEP 2: Calculate commission and due instant

**Actor**: Commission service
**Action**: Apply the active affiliate contract and tax calculation. For a payable sale, set `available_at` to `good_date` at 00:00 UTC. Create the commission as `pending`, even if it is already due; the scheduled process handles all due pending rows.
**Timeout**: Same transaction/request budget as the event operation.
**Input**: Persisted sale event and applicable affiliate/contract.
**Output on SUCCESS**: One commission row with currency, amounts, `pending`, and `available_at` -> STEP 3.
**Output on FAILURE**:
- `FAILURE(no_commission_term)`: Keep the event without a payable commission; record the existing non-payable reason if the event contract supports it.
- `FAILURE(unsupported_currency)`: Keep the event visible but do not create a payable commission.
- `FAILURE(database)`: Roll back the commission transaction. If the event was already committed, keep it and retry commission generation on the same idempotent event retry; if event and commission share an uncommitted transaction in a future implementation, roll back both.

**Observable states**:
- Affiliate sees a pending commission only when a commission was produced.
- Merchant sees the event and linked commission, or the non-payable event reason.
- Database contains one event and either one pending commission or no commission.
- Logs include event/commission IDs and reason; avoid customer PII.

### STEP 3: Run daily maturity scan

**Actor**: Daily scheduler and commission service
**Action**: At least once each UTC day, select `pending` commissions where the stored/derived UTC due instant is `<= now_utc`, update them to `available`, and commit atomically. Exclude any commission linked to a payout in `pending_approval` or `approved`, even if a legacy App Runner instance left its stored status as `pending` or `PayoutCommission.is_active=false`. When `available_at` is null on a legacy-created row, derive it from the source sale's `good_date`. The transitional `available_on` column was dropped by contract migration `a1b2c3d4e5f6`. Do not alter `reserved`, `paid`, or `reversed` states.
**Timeout**: 10 minutes for the one-shot job. The job cancels the active database transaction on timeout, exits non-zero, and relies on the next daily run to catch up.
**Input**: Scheduled run ID and UTC start timestamp.
**Output on SUCCESS**: Number of examined/promoted rows and completion timestamp -> END.
**Output on FAILURE**:
- `FAILURE(database_or_transient)`: Roll back the affected transaction/batch, mark the run failed, alert/record an operational error, and allow the next daily run to catch up.
- `FAILURE(timeout)`: Do not mark uncommitted rows available; retry the run or rely on the next scheduled catch-up run.
- `FAILURE(duplicate_run)`: Concurrent/repeated execution is safe; conditional state update/locking means each due commission transitions once.

**Observable states**:
- Affiliate balance changes only after a successful database commit.
- Operator can see run start, finish/failure, examined count, promoted count, and error without exposing affiliate/customer secrets.
- Database changes only committed `pending -> available` rows; failed batches remain pending for retry.
- Logs carry run ID, timing, counts, and error class.

## State transitions

```text
sale event accepted + applicable contract -> commission pending
commission pending + available_at <= now_utc + successful daily run -> available
commission pending + invalid/missing good_date or external payment_record_id -> no payable commission; event rejected if required sale field is absent
```

Payout reservation and payment transitions are specified in `WORKFLOW-affiliate-payout-request.md` and `WORKFLOW-merchant-payout-settlement.md`.

## Handoff contracts

### Merchant integration -> Event API

- **Endpoint**: `POST /api/v1/events`
- **Required sale fields**: `event_id`, `type=sale`, attribution fields required by the event contract, amount, currency, payment sequence, `good_date`, and external `payment_record_id`.
- **Correlation**: preserve `payment_record_id` on the event for future refund correlation; do not require or create a Rosulo incoming-payment row.
- **Success**: accepted event with event ID and commission-generation result.
- **Failure**: validation/authentication response; retryable infrastructure failure may be retried with the same event ID.
- **Timeout**: API runtime request timeout.
- **Recovery**: retry transient failures idempotently; correct and resubmit validation failures with the same logical event ID.

### Daily scheduler -> Commission maturity process

- **Payload**: `{run_id, scheduled_at_utc}`.
- **Success**: `{run_id, examined_count, promoted_count, completed_at_utc}`.
- **Failure**: `{run_id, error_code, retryable}` in scheduler logs/monitoring; no partial status transition for rolled-back batch.
- **Timeout**: 10 minutes inside the job; EventBridge Scheduler also uses a 1-hour delivery age, two target-delivery retries, and a DLQ for RunTask invocation failures.
- **Recovery**: Retry transient failures; subsequent daily run catches up due rows.

## Cleanup inventory

The workflow creates no external resources. Database writes are transactional. If commission calculation fails before commit, roll back newly created event/commission rows together when possible; if an event was already committed separately, an idempotent retry must resume without duplicating it.

| Resource | Created at step | Failure cleanup |
|---|---|---|
| Event row | Step 1 | Transaction rollback when uncommitted; retain an already committed valid event |
| Commission row | Step 2 | Transaction rollback when uncommitted; never delete a committed ledger row as retry cleanup |
| Availability status update | Step 3 | Roll back affected batch/transaction; later run catches up |

## Reality review findings

| # | Finding | Severity | Resolution |
|---|---|---|---|
| R-1 | Current `EventCreate.good_date` is optional, and commission code currently computes `available_on = (good_date or today) + 14 days`. | High | Resolved 2026-10-02: `good_date` and `payment_record_id` are required on sale events; `available_at` is UTC midnight of `good_date`; `available_on` dropped by `a1b2c3d4e5f6`. |
| R-2 | Current promotion helper runs lazily during payout requests and uses `date.today()`; no daily scheduler was found in `backend/app`. | High | Resolved 2026-10-02: `backend/app/jobs/payout_maintenance.py` runs daily via EventBridge/ECS Fargate at 00:15 UTC with catch-up semantics. |
| R-3 | Current payout reservation uses `pending`, sharing the state with maturity. | Medium | Resolved 2026-10-02: distinct `reserved` commission status added in `e8f9a0b1c2d3`. |

## Test cases

| Test | Trigger | Expected behavior |
|---|---|---|
| CM-01 | Sale with valid good_date, supported currency, matching term | Exactly one pending commission; available_at equals UTC midnight of good_date |
| CM-02 | Sale missing good_date or external payment_record_id | Validation failure; no event/commission is payable |
| CM-03 | Sale good_date is in the future | Commission stays pending after daily run |
| CM-04 | Sale good_date is due or in the past | Next successful daily run marks it available once |
| CM-05 | Same event retried in same tenant | Original event returned; no duplicate commission |
| CM-06 | Due legacy `pending` commission is linked to active payout | It remains reserved/logically reserved and is not promoted |
| CM-07 | Two maturity runs overlap | Commission changes to available once; no unrelated status is changed |
| CM-08 | Database failure during promotion | Affected uncommitted rows remain pending; next run catches up |
| CM-09 | No matching commission term or unsupported currency | Event remains visible; no payable commission is created |

## Assumptions and open questions

| # | Assumption / question | Resolution |
|---|---|---|
| A1 | `good_date` is date-only and due at 00:00 UTC. | Confirmed by product owner on 2026-10-01. |
| A2 | Merchant sends the sale event only after payment confirmation. | Confirmed by product owner on 2026-10-01. |
| D1 | Scheduler and timeout | EventBridge Scheduler launches ECS/Fargate at 00:15 UTC daily; the job has a 10-minute timeout, two invocation retries, and a DLQ. Deploy/verify before launch. |
| O2 | A new refund event will reference the prior sale's external `payment_record_id`. | Confirmed by product owner; refund workflow remains out of scope here. |

## Spec vs reality audit log

| Date | Finding | Action taken |
|---|---|---|
| 2026-10-01 | Initial target workflow differs from current lazy 14-day `available_on` implementation. | Documented as Review; implementation remains pending. |
| 2026-10-02 | Implemented by `2026-10-01-commission-availability-and-request-implementation-plan.md` on `feature/commission-availability-and-request`, with contract migration `a1b2c3d4e5f6`. | Backend 176 tests pass; scheduler stack validated; non-production Fargate run remains a deployment release-gate. |
