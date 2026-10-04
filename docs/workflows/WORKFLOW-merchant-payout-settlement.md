# WORKFLOW: Merchant Payout Review and Manual Settlement

**Version**: 1.0
**Date**: 2026-10-01
**Author**: Workflow design
**Status**: Implemented
**Implements**: Commission-backed manual payout product design

## Overview

A tenant user reviews an affiliate's exact commission batch, then approves or rejects it. An approved payout is paid outside Rosulo through PayPal; the merchant records the actual payment datetime and PayPal reference in Rosulo. A committed payment creates one `PayoutPayment`, marks the payout and linked commissions paid, and triggers an affiliate email with a payout-detail link.

## Actors

| Actor | Role |
|---|---|
| Affiliate | Creates request and receives status/payment notice |
| Merchant reviewer / payer | Reviews batch, approves/rejects, manually transfers, records payment |
| Admin Payout API/UI | Tenant-scoped review and payment-confirmation interface |
| Payout service | Validates state and applies atomic transitions/payment record |
| Database | Persists payout, commission links/statuses, transition history, and `PayoutPayment` |
| Email service | Delivers transactional paid notice after commit |

## Prerequisites

- Payout exists, is scoped to the merchant tenant, and is `pending_approval` for review.
- Affiliate is associated with the same tenant; payment profile contains a PayPal recipient identifier before transfer.
- `PayoutCommission` rows and derived totals are consistent with the reserved commission set.
- Payment confirmation is allowed only for an `approved` payout.
- No Rosulo PayPal API call or SQS payout dispatch is part of this workflow.

## Triggers

- Merchant opens a pending payout detail in the admin UI.
- Merchant chooses approve or reject.
- Merchant completes PayPal transfer outside Rosulo and submits payment datetime plus PayPal transaction/reference.

## Workflow tree

### STEP 1: Load tenant-scoped payout and itemized review

**Actor**: Admin Payout API/UI
**Action**: Fetch the payout, affiliate identity, all linked commissions, source sale dates, aggregate amounts, count, and commission date range; enforce tenant scope.
**Timeout**: API runtime request timeout.
**Input**: Authenticated tenant user and payout ID.
**Output on SUCCESS**: Complete review view -> STEP 2.
**Output on FAILURE**:
- `FAILURE(not_found_or_wrong_tenant)`: Return 404 without exposing cross-tenant existence.
- `FAILURE(inconsistent_association)`: Return an actionable internal error and surface to operator; do not allow approval/payment.
- `FAILURE(database_or_timeout)`: Return retryable server error; no mutation.

**Observable states**:
- Affiliate sees existing `pending_approval` state.
- Merchant sees full commission records, source-sale date range, count, gross, withholding, and net totals.
- Database is read-only.
- Logs include tenant/user/payout IDs and trace ID.

### STEP 2: Approve or reject request

**Actor**: Merchant reviewer and payout service
**Action**: Lock payout, revalidate tenant and `pending_approval`, lock/validate every linked commission is `reserved`, then apply one legal decision and append one transition.

**Output on APPROVE**: Set payout `approved` and `approved_at`; keep commissions `reserved`; commit atomically -> STEP 3.

**Output on REJECT**: Set payout `rejected`; transition each linked `reserved` commission to `available`; preserve every `PayoutCommission` link and audit transition; commit atomically -> END.

**Failure branches**:
- `FAILURE(already_decided)`: If another action committed first, return 409; no second state change.
- `FAILURE(reservation_inconsistent)`: Return 409 and alert operator; do not partially approve/reject or release an incomplete set.
- `FAILURE(database)`: Roll back payout transition and all commission status updates.

**Observable states**:
- Affiliate sees approved or rejected status after commit; rejected commissions return to available balance.
- Merchant sees the updated payout status and transition history.
- Database contains either the complete decision or no decision; rejected historical payout links remain.
- Logs record prior/new status, reviewer, and outcome.

### STEP 3: Prepare external PayPal payment

**Actor**: Merchant payer and admin UI
**Action**: For an `approved` payout, open a confirmation modal prefilled with affiliate name, contact email, PayPal recipient identifier, payout net amount/currency, and commission count. Merchant transfers funds outside Rosulo.
**Timeout**: Human-operated step; no service timeout.
**Input**: Approved payout and current affiliate payment profile.
**Output on SUCCESS**: Merchant confirms transfer completed and enters actual `paid_at` plus PayPal reference -> STEP 4.
**Output on FAILURE**:
- `FAILURE(missing_recipient)`: Do not present the transfer as ready; block confirmation until recipient identity is present/corrected.
- `FAILURE(merchant_does_not_transfer)`: Leave payout approved and commissions reserved; no payment record is created.
- `FAILURE(stale_profile_or_amount)`: Refresh payout and affiliate details before external transfer; never change the approved commission set implicitly.

**Observable states**:
- Affiliate sees `approved`, not `paid`.
- Merchant sees beneficiary/amount instructions and has not yet recorded a completed payment.
- Database payout remains approved; commissions remain reserved; no `PayoutPayment` exists.
- Logs contain modal open/close events only if product telemetry is implemented; never log full recipient PII unnecessarily.

### STEP 4: Confirm external payment atomically

**Actor**: Admin Payout API and payout service
**Action**: Validate actual payment datetime and nonblank PayPal reference; lock payout and commissions; require payout `approved` and every commission `reserved`; create one `PayoutPayment` with derived payout amount/currency, fixed method `paypal`, reference, merchant-supplied `paid_at`, and confirming tenant user; do not snapshot the PayPal recipient; mark payout `paid` and commissions `paid`; append transition; commit atomically.
**Timeout**: API/database transaction timeout.
**Input**: `{paid_at, transfer_reference}` plus authenticated tenant user and payout ID. The client cannot supply amount or currency.
**Output on SUCCESS**: Paid payout and one payment record -> STEP 5.
**Output on FAILURE**:
- `FAILURE(invalid_input)`: Reject invalid datetime or blank/oversized reference; no mutation.
- `FAILURE(wrong_status)`: Only approved payouts can be confirmed; return 409/400 according to API contract; no mutation.
- `FAILURE(reservation_inconsistent)`: Return 409 and alert operator; no partial payment.
- `FAILURE(identical_retry)`: Return the existing paid payout when stored paid_at/reference match; do not create another payment or transition.
- `FAILURE(conflicting_retry)`: Return 409 when a paid payout is submitted with different details; preserve original record.
- `FAILURE(database)`: Roll back PayoutPayment, payout state, commission states, and transition together.

**Observable states**:
- Affiliate sees `paid` only after the transaction commits.
- Merchant sees payment confirmation and immutable recorded date/reference.
- Database has exactly one `PayoutPayment`, payout `paid`, all linked commissions `paid`, and one transition, or remains approved with commissions reserved.
- Logs include actor, payout ID, payment-record ID, and outcome; mask/reference access follows tenant audit policy.

### STEP 5: Send affiliate paid email

**Actor**: Notification delivery process
**Action**: The payment transaction creates one durable `PayoutNotification(status=pending)`. After commit, a FastAPI background task claims it as `sending` with a 10-minute lease, then sends a transactional email with payout amount/currency and an authenticated payout detail URL containing the non-secret tenant ID context. The API task uses SES connect/read timeouts of 5/15 seconds and one provider attempt; it records `sent` after provider acceptance or `failed` with a safe error code. A merchant can retry failed notices; the daily maintenance task recovers pending rows and expired `sending` leases.
**Timeout**: SES request deadline 20 seconds; background task does not alter the already-committed payment state.
**Input**: Payout/payment IDs, affiliate email, amount/currency, secure application detail URL.
**Output on SUCCESS**: Notification marked delivered -> END.
**Output on FAILURE**:
- `FAILURE(transient_or_permanent)`: Mark the notification `failed` with attempt time and sanitized error code; leave the payout paid and expose the merchant retry action.
- `FAILURE(process_crash)`: The row remains `sending`; after its 10-minute lease expires, the next daily maintenance run resets it to pending and retries.
- `FAILURE(duplicate_delivery)`: SES may accept a message before the DB status update is committed; a lease recovery can send a duplicate. Keep duplicate emails harmless and never duplicate the payment record.

**Observable states**:
- Affiliate payout detail remains authoritative even before email arrives.
- Merchant sees notification state `pending`, `sending`, `sent`, or `failed`; failed state exposes an explicit retry action.
- Database remains paid regardless of email outcome; the notification row is durable and retryable independently.
- Logs include notification ID and result, not message body or secrets.

## State transitions

```text
pending_approval -> approved -> paid
pending_approval -> rejected
approved -> approved (while merchant performs external transfer; no status change)
rejected -> terminal; released commissions may be requested again under a new payout
paid -> terminal; corrections require a separately designed audited workflow
```

## Handoff contracts

### Merchant UI -> Payout API (approval/rejection)

- **Endpoints**: Existing `POST /api/v1/admin/payouts/{id}/approve` and `/reject`.
- **Payload**: No client-supplied totals; rejection reason may be included if supported by approved product policy.
- **Success**: Updated payout with transition and itemized associations.
- **Failure**: 404 for absent/cross-tenant, 409 for stale state/reservation conflict, retryable 5xx for transient DB failure.
- **Timeout**: API runtime request timeout.
- **Recovery**: Refetch current payout on conflict; never retry an incompatible state transition blindly.

### Merchant UI -> Payout API (payment confirmation)

- **Endpoint**: `POST /api/v1/admin/payouts/{id}/confirm-payment`.
- **Payload**: `paid_at` (timezone-aware datetime) and `transfer_reference` (required PayPal transaction/reference); method is fixed to PayPal, amount/currency come from payout.
- **Success**: Payout with `paid` state and one `PayoutPayment`.
- **Failure**: 400/422 validation, 403 tenant mismatch, 404 hidden cross-tenant resource, 409 invalid transition/inconsistent reservation/conflicting retry, retryable 5xx on database failure.
- **Timeout**: API/database transaction timeout.
- **Recovery**: On network uncertainty, repeat the same values; the service returns the existing result if identical.

### Payment commit -> Email delivery

- **Payload**: `{notification_id, affiliate_id, payout_id, email, amount, currency, payout_url}`.
- **Success**: Delivery ID/status recorded.
- **Failure**: `{notification_id, status: failed, error_code}`; payment remains committed.
- **Timeout**: 20 seconds for SES connect/read combined.
- **Recovery**: Merchant may retry a failed notification; the daily ECS job recovers pending rows or sending leases expired for at least 10 minutes. A repeated email does not create a second payment.

## Cleanup inventory

No external payment resource is created by Rosulo. Payment is performed by the merchant outside the platform. Before DB commit, a failed confirmation rolls back all payment/ledger mutations. After commit, email failure is recovered by retry and must never delete the payment record or reverse payout state.

| Resource | Created at step | Cleanup/recovery |
|---|---|---|
| Payout transition | Step 2/4 | Roll back if transaction fails; retain committed history |
| PayoutPayment | Step 4 | Roll back if transaction fails; committed record is immutable; corrections require separate audited workflow |
| Commission status changes | Step 2/4 | Roll back atomically on failed commit; reject releases only on a committed rejection |
| Email notification | Step 5 | Retry/mark failed; never roll back paid status |

## Reality review findings

| # | Finding | Severity | Resolution |
|---|---|---|---|
| R-1 | Current W0.2 code stores payout confirmation in `PaymentRecord`, sets payment time to server now, and accepts generic method/reference fields. | High | Create `PayoutPayment`; accept merchant-entered paid_at/reference; fix method to PayPal and retain the value as requested by product. |
| R-2 | Current payout detail does not return/display full commission record details and affiliate PayPal recipient context for manual payment. | High | Add the itemized review and beneficiary summary. |
| R-3 | Current email service has templates/sending support but no payout notification workflow was found. | Medium | Add after-commit retryable notification. |
| R-4 | Current incoming-payment webhook persists `PaymentRecord` rows, but intended product makes sale event the post-confirmation input. | High | Retire ingestion/storage while preserving event external `payment_record_id`; migrate payout-linked records and safely handle legacy data. |
| R-5 | Current merchant reporting does not provide paid payout totals by affiliate for rolling 12 months and YTD. | Medium | Add payment-date scoped, per-currency aggregates. |

## Test cases

| Test | Trigger | Expected behavior |
|---|---|---|
| MPS-01 | Merchant loads own pending payout | Full commission detail, totals, count, and source-sale date range visible |
| MPS-02 | Merchant requests payout belonging to another tenant | 404/forbidden response; no foreign data |
| MPS-03 | Approve pending payout | Payout approved; commissions remain reserved; no PayPal API/SQS dispatch |
| MPS-04 | Reject pending payout | Payout rejected; all linked commissions released exactly once; history remains |
| MPS-05 | Approve/reject same payout concurrently | One transition commits; other receives conflict |
| MPS-06 | Approved payout missing PayPal recipient | Modal/confirmation blocked with actionable message |
| MPS-07 | Confirm manual payment with valid paid_at/reference | One PayoutPayment; payout/commissions paid atomically |
| MPS-08 | Confirm identical payment twice | Existing paid payout returned; no duplicate payment/transition |
| MPS-09 | Confirm with conflicting reference after paid | 409; original payment remains unchanged |
| MPS-10 | Confirm pending/rejected payout or inconsistent commission links | Reject without any partial state change |
| MPS-11 | Payment commit succeeds, email send fails transiently | Payout remains paid; notification is retryable and observable |
| MPS-12 | Merchant affiliate history report spans rolling 12 months/YTD | Totals match paid_at rows and remain separated by currency |
| MPS-13 | Incoming-payment webhook is called after retirement | Route is unavailable/explicitly retired; sale event's external ID remains accepted and stored |
| MPS-14 | Migration encounters payout-linked legacy PaymentRecord | PayoutPayment is preserved exactly; no payout payment data loss |
| MPS-15 | Migration encounters legacy incoming PaymentRecord rows | Migration preserves/archive-exports them or fails closed pending retention decision |

## Assumptions and open questions

| # | Assumption / question | Resolution |
|---|---|---|
| A1 | Merchant enters the actual payment datetime; Rosulo does not substitute confirmation time. | Product owner requirement. |
| A2 | PayoutPayment amount equals the approved payout's derived net amount and cannot be independently edited. | Product design decision. |
| A3 | Email is sent after commit, has a secure authenticated detail link, and cannot change payment state. | Product owner confirmed email with detail link. |
| A4 | Paid totals use payment date, rolling 12 months and calendar YTD, grouped by currency. | Product owner confirmed paid-payout interpretation. |
| D1 | Notification record is committed with payment; immediate BackgroundTask sends; merchant can retry failed; daily Fargate run recovers pending/expired sending leases. | Confirmed in implementation plan; SES connect/read timeouts are 5/15 seconds. |
| O2 | Existing incoming payment rows require retention review before table removal. | Migration must fail closed or preserve rows; no silent deletion. |
| D2 | Use the current affiliate profile PayPal email in the modal; do not retain a recipient snapshot in `PayoutPayment`. | Resolved to minimize retained PayPal recipient PII; merchant verifies recipient before transfer. |

## Spec vs reality audit log

| Date | Finding | Action taken |
|---|---|---|
| 2026-10-01 | Initial target settlement flow is manual merchant PayPal, not provider execution; existing model conflates incoming payments and payouts. | Documented as Review; implementation remains pending. |
| 2026-10-02 | Implemented by `2026-10-01-merchant-manual-payout-operations-implementation-plan.md` on `feature/merchant-manual-payout-operations`; `payment_records` storage retired by contract migration `a1b2c3d4e5f6` (fails closed on unresolved `incoming_payment` rows). | Backend 176 tests pass, frontend 42 tests pass, build green; expand/contract rollout order applies at deploy time. |
