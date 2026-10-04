# WORKFLOW: Affiliate Payout Request

**Version**: 1.0
**Date**: 2026-10-01
**Author**: Workflow design
**Status**: Implemented
**Implements**: Commission-backed manual payout product design

## Overview

An eligible affiliate selects all currently available commissions of a currency or a set of whole commission IDs. Rosulo derives payout totals from the ledger and atomically reserves the selected rows in one `pending_approval` payout. A commission cannot be reserved by another active payout; rejected requests retain historical links but release commissions for later requests.

## Actors

| Actor | Role |
|---|---|
| Affiliate | Chooses all or selected eligible commission rows |
| Affiliate API | Authenticates affiliate/tenant context and validates selection |
| Payout service | Locks commissions, derives totals, and creates payout plus links |
| Database | Enforces tenant scope, currency, uniqueness, and atomic state changes |
| Merchant reviewer | Reviews, approves, or rejects the payout in the separate settlement workflow |

## Prerequisites

- Affiliate is authenticated and has selected the tenant.
- Affiliate's tenant-specific payout eligibility is approved.
- At least one commission is in `available` status.
- Every payout contains commissions in exactly one supported currency.
- Commission maturity workflow has promoted due commissions; payout creation must not be the only mechanism that promotes commissions.

## Trigger

Affiliate confirms a payout request in the UI or submits the payout request API.

**Request contract intent**:

```json
{
  "currency": "USD",
  "commission_ids": ["uuid-1", "uuid-2"]
}
```

Omit `commission_ids` to select all available commissions for that affiliate/currency. If present, it must be a non-empty list of unique IDs. No amount field is accepted.

## Workflow tree

### STEP 1: Validate identity, eligibility, and selection shape

**Actor**: Affiliate API
**Action**: Resolve affiliate from authentication and active tenant. Validate payout eligibility, currency, and request shape.
**Timeout**: API runtime request timeout.
**Input**: Currency and optional commission IDs.
**Output on SUCCESS**: Normalized selection intent -> STEP 2.
**Output on FAILURE**:
- `FAILURE(unauthorized)`: No valid affiliate session -> 401; no database mutation.
- `FAILURE(ineligible)`: Per-tenant payout eligibility is false -> 403 with reason; no database mutation.
- `FAILURE(invalid_selection)`: Invalid currency, empty IDs, duplicate IDs, or malformed request -> 422; no database mutation.
- `FAILURE(no_available_commissions)`: No eligible commission rows match -> 400/no-available response; no payout is created.

**Observable states**:
- Affiliate sees validation or eligibility explanation, or proceeds to confirmation.
- Merchant sees no request until persistence succeeds.
- Database is unchanged during validation.
- Logs include affiliate/tenant IDs and error class, never tokens or payment account secrets.

### STEP 2: Lock and validate selected commissions

**Actor**: Payout service and database
**Action**: Resolve either all `available` rows for the affiliate/currency or the exact requested IDs. Lock rows in deterministic order. Verify every selected ID belongs to the authenticated affiliate and tenant, is `available`, and matches currency.
**Timeout**: Included in API request budget.
**Input**: Validated selection intent.
**Output on SUCCESS**: Exact locked set and ledger values -> STEP 3.
**Output on FAILURE**:
- `FAILURE(not_found_or_wrong_owner)`: Any selected row is not owned by this affiliate/tenant -> 404 or generic invalid-selection response; no partial reservation.
- `FAILURE(no_longer_available)`: Any selected row was reserved/paid/reversed or concurrently changed -> 409; no payout is created.
- `FAILURE(mixed_currency)`: Any selected row currency differs from request -> 422; no payout is created.
- `FAILURE(lock_timeout_or_database)`: Roll back; caller may retry after transient failure.

**Observable states**:
- Affiliate sees a conflict and can refresh selection.
- Merchant sees no partial payout.
- Database retains all commission statuses unchanged if validation fails.
- Logs include payout-selection counts and conflict reason without leaking customer PII.

### STEP 3: Create payout and reserve commission rows atomically

**Actor**: Payout service and database
**Action**: Derive gross, withholding, and net from exact commission rows; create `Payout(status=pending_approval)` and all payout-commission links; change selected commissions `available -> reserved`; record the initial payout transition. Commit as one transaction.
**Timeout**: Included in API request budget.
**Input**: Locked set of available commission rows.
**Output on SUCCESS**: Payout with immutable selected-commission association and derived totals -> STEP 4.
**Output on FAILURE**:
- `FAILURE(database_or_constraint)`: Roll back payout, association rows, commission status updates, and transition together.
- `FAILURE(concurrent_conflict)`: At most one request commits for a given commission set; losing request returns 409 and creates no payout.

**Observable states**:
- Affiliate sees request pending merchant approval with itemized details.
- Merchant queue shows the request only after commit.
- Database has one payout, complete association rows, `reserved` commission statuses, and transition sequence 1, or none of those changes.
- Logs include payout ID, tenant/affiliate IDs, currency, count, and totals.

### STEP 4: Merchant decision handoff

**Actor**: Merchant reviewer
**Action**: Present request for detailed review. Approve/reject actions are defined in `WORKFLOW-merchant-payout-settlement.md`.
**Timeout**: Not applicable to the completed affiliate request; merchant review may be asynchronous.
**Input**: Persisted payout ID.
**Output on SUCCESS**: Merchant sees the exact requested batch and can make a decision.
**Output on FAILURE**: Missing/tenant-mismatched payout is not exposed; merchant receives not found/authorization response.

**Observable states**:
- Affiliate sees `pending_approval`.
- Merchant sees the commission rows, count, date range, and financial totals.
- Database remains unchanged until the merchant action.
- Logs record read/action audit IDs.

## State transitions

```text
Commission available -> reserved when request transaction commits
No matching / invalid selection -> no payout and no commission mutation
Payout pending_approval -> approved or rejected in merchant workflow
Rejected payout: reserved commission -> available; prior PayoutCommission links remain as history
Approved payout: commission remains reserved until confirmed paid
Paid payout: reserved commission -> paid
```

## Handoff contracts

### Affiliate UI -> Affiliate payout API

- **Endpoint**: Existing `POST /api/v1/affiliate/payout-requests`; exact route response may be versioned during implementation.
- **Payload**: `{currency: string, commission_ids?: UUID[]}`.
- **Success**: Created payout with ID/status, totals, currency, timestamps, and itemized commission detail.
- **Failure**: 401, 403, 404/422 for invalid selection, 409 for stale/concurrent reservation, 400 for no available commissions.
- **Timeout**: API runtime request timeout.
- **Recovery**: Retry transient failures idempotently using request idempotency strategy established in the implementation plan; refresh and reselect on a reservation conflict.

### Payout service -> Database

- **Payload**: Payout header, linked commission IDs/amounts, initial transition, and conditional commission status changes.
- **Success**: All rows commit in one transaction.
- **Failure**: Transaction rollback; no partial payout reservation.
- **Timeout**: Database statement/transaction timeout configured by the application.
- **Recovery**: Retry only transient transaction failures; re-read commission availability before retry.

## Cleanup inventory

| Resource | Created at step | Cleanup on failure |
|---|---|---|
| Payout row | Step 3 | Transaction rollback before commit; committed payouts are never deleted as failure cleanup |
| PayoutCommission rows | Step 3 | Transaction rollback before commit; retain committed associations for audit |
| Commission `reserved` state | Step 3 | Transaction rollback before commit; after committed rejection, explicitly transition back to `available` |
| Payout transition | Step 3 | Transaction rollback before commit; preserve committed history |

## Reality review findings

| # | Finding | Severity | Resolution |
|---|---|---|---|
| R-1 | Current affiliate request accepts currency only and reserves all available commissions; it has no selected-ID contract. | High | Add whole-commission selection and itemized request details. |
| R-2 | Current code stores payout-reserved commissions as `pending`, while `pending` also means not yet mature. | High | Separate `reserved` from `pending` in state model and balance projections. |
| R-3 | Existing service has a `PayoutCommission` association but no constraint documented here that prevents simultaneous active associations. | High | Lock/status-validate rows and enforce the active-reservation invariant in the database/application design. |

## Test cases

| Test | Trigger | Expected behavior |
|---|---|---|
| APR-01 | Omit IDs with available commissions in one currency | All and only those commissions are reserved; totals reconcile |
| APR-02 | Select a subset of available commission IDs | Only selected whole commissions are linked and reserved |
| APR-03 | Submit amount field or empty selection | Reject; no payout or commission mutation |
| APR-04 | ID belongs to another affiliate/tenant | Reject without disclosing another affiliate's data; no payout |
| APR-05 | Selected ID is pending, reserved, paid, or reversed | Reject entire request; no partial payout |
| APR-06 | Select mixed currency | Reject entire request; no payout |
| APR-07 | Duplicate commission IDs | Validation failure; no payout |
| APR-08 | Two requests race for the same commission | Exactly one commits; other receives conflict; no duplicate active association |
| APR-09 | Commission request fails during transaction | No payout/link/status/transition partial writes remain |
| APR-10 | Merchant rejects, affiliate requests released commission later | New payout can link it; rejected payout and original association remain visible |
| APR-11 | Affiliate is not payout eligible | 403 with policy reason; no financial mutation |

## Assumptions and open questions

| # | Assumption / question | Resolution |
|---|---|---|
| A1 | Missing `commission_ids` means all available in the required currency; an empty list is invalid. | Product design decision. |
| A2 | Date range shown by the payout uses source sale event `occurred_at` in UTC. | Product design assumption; confirm when reviewing merchant detail UI. |
| A3 | Payout currency remains single-currency; no FX conversion. | Existing ledger invariant. |
| O1 | API idempotency key/response behavior for client retries must be selected in implementation planning. | Resolve before API implementation. |

## Spec vs reality audit log

| Date | Finding | Action taken |
|---|---|---|
| 2026-10-01 | Initial target request workflow differs from current currency-only request. | Documented as Review; implementation remains pending. |
| 2026-10-02 | Implemented by `2026-10-01-commission-availability-and-request-implementation-plan.md` on `feature/commission-availability-and-request`. | All/selected whole-commission requests with atomic reservation verified; backend 176 tests pass. |
