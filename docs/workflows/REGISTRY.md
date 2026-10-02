# Workflow Registry — Affiliate Payout Domain

**Date:** 2026-10-01
**Status:** Focused registry for commission maturity and payout workflows; not a full-project workflow audit.
**Source of product behavior:** `docs/superpowers/specs/2026-10-01-commission-backed-manual-payouts-design.md`

This registry maps the three payout-domain workflows specified for the next implementation phase. Unrelated authentication, invitation, event attribution, tax review, and refund workflows have not been audited here. Workflow specs remain in `Review` until implementation and reality review close the documented gaps.

## Workflows

| Workflow | Spec file | Status | Trigger | Primary actor | Last reviewed |
|---|---|---|---|---|---|
| Commission maturity | `WORKFLOW-commission-maturity.md` | Review | Sale event with merchant `good_date` and external `payment_record_id`; EventBridge ECS/Fargate run at 00:15 UTC daily | Merchant integration / scheduled service | 2026-10-01; code divergence recorded |
| Affiliate payout request | `WORKFLOW-affiliate-payout-request.md` | Review | Affiliate submits all or selected available commissions | Affiliate | 2026-10-01; selection gap recorded |
| Merchant payout review and manual settlement | `WORKFLOW-merchant-payout-settlement.md` | Review | Merchant reviews request and later records external PayPal payment | Merchant user | 2026-10-01; payment-record/notification gaps recorded |
| Refund and commission reversal | Not yet specified | Missing | Future refund event references a prior sale's external `payment_record_id` | Merchant integration | — |

## Components

| Component | Current / planned file(s) | Workflows |
|---|---|---|
| Sale event intake | `backend/app/api/v1/public/events.py`, `backend/app/services/event.py`, `backend/app/schemas/event.py` | Commission maturity |
| Commission ledger and due promotion | `backend/app/services/commission.py`, `backend/app/db/models.py`, `backend/app/jobs/payout_maintenance.py`; EventBridge/Fargate schedule planned | Commission maturity, affiliate payout request, merchant settlement |
| Affiliate payout request API/service | `backend/app/api/v1/affiliate/payouts.py`, `backend/app/services/payout.py`, `backend/app/schemas/payout.py` | Affiliate payout request |
| Merchant payout review/payment API | `backend/app/api/v1/admin/payouts.py`, `backend/app/services/payout.py`, `backend/app/schemas/payout.py` | Merchant payout review and manual settlement |
| Payout persistence and audit | `backend/app/db/models.py`, `backend/alembic/versions/` | Affiliate payout request, merchant payout review and manual settlement |
| Payout UI | `frontend/src/pages/admin/PayoutsPage.tsx`, `frontend/src/components/admin/PayoutDetail.tsx`, `frontend/src/components/admin/PayoutQueue.tsx`, `frontend/src/components/affiliate/PayoutsTable.tsx` | Affiliate payout request, merchant payout review and manual settlement |
| Payment email and notification state | `backend/app/services/email.py`, payout email templates, `PayoutNotification`, `backend/app/jobs/payout_maintenance.py` | Merchant payout review and manual settlement |
| Incoming payment persistence | `backend/app/api/v1/public/webhooks.py`, `backend/app/services/payment_record.py`, `PaymentRecord` in `backend/app/db/models.py` | Current implementation only; planned retirement from sale/payout lifecycle |
| Affiliate reporting | `backend/app/services/dashboard.py`, dashboard APIs and pages | Merchant payout review and manual settlement |

## User journeys

### Affiliate journey

| Experience | Workflow(s) | Entry point |
|---|---|---|
| Views commissions becoming eligible | Commission maturity | Affiliate balance/commission views |
| Requests payment for all or selected commissions | Affiliate payout request | Affiliate payout request UI/API |
| Reviews pending/approved/rejected/paid payout and payment reference | Affiliate payout request -> Merchant payout settlement | Affiliate payout history/detail |
| Opens payment email and verifies payout | Merchant payout settlement | Transactional email link to authenticated payout detail |

### Merchant journey

| Experience | Workflow(s) | Entry point |
|---|---|---|
| Reviews exact commission batch and approves/rejects | Affiliate payout request -> Merchant payout settlement | Admin payout queue/detail |
| Pays affiliate manually using PayPal and records payment | Merchant payout settlement | PayPal modal on approved payout |
| Checks affiliate's payout history and paid totals | Merchant payout settlement | Affiliate detail/history |

### System-to-system journey

| Automatic action | Workflow(s) | Trigger |
|---|---|---|
| Promotes due pending commissions | Commission maturity | EventBridge Scheduler launches ECS/Fargate at 00:15 UTC daily (planned, not deployed) |
| Sends affiliate paid notice | Merchant payout settlement | Payment transaction committed |
| Associates future refund with source sale | Refund and commission reversal | Future refund event; workflow is Missing |

## State map

| State | Entered by | Exited by | Workflows that trigger exit |
|---|---|---|---|
| Commission `pending` | Payable sale event with required `good_date` | `available` | Daily maturity when `available_at <= now_utc` |
| Commission `available` | Successful due-commission promotion or rejected payout release | `reserved` | Affiliate payout request |
| Commission `reserved` | Payout request commits | `available` or `paid` | Merchant rejection or confirmed payment |
| Commission `paid` | Confirmed payment of approved payout | Terminal in this lifecycle | Corrections require separate audited workflow |
| Commission `reversed` | Existing/future reversal processing | Future policy required | Refund/reversal workflow is Missing |
| Payout `pending_approval` | Affiliate payout request commits | `approved` or `rejected` | Merchant review |
| Payout `approved` | Merchant approval | `paid` | Merchant confirms completed PayPal transfer |
| Payout `rejected` | Merchant rejection | Terminal payout; commissions released | New request creates a new payout association |
| Payout `paid` | Manual payment confirmation commits | Terminal in this lifecycle | Corrections require separate audited workflow |
| PayoutNotification `pending` | Same transaction as confirmed payment | `sending` | Background email delivery or maintenance recovery |
| PayoutNotification `sending` | Delivery attempt claims a valid lease | `sent`, `failed`, or `pending` after lease expiry | Email delivery, failure handling, or daily maintenance recovery |
| PayoutNotification `sent` | Email provider accepts message | Terminal | — |
| PayoutNotification `failed` | Provider error recorded | `pending` | Merchant retries notification |

## Discovery audit — payout scope

| Area scanned | Finding | Status |
|---|---|---|
| Payout/event API entry points | Sale event and affiliate/admin payout routes exist; incoming-payment webhook exists | Scanned for relevant routes |
| Background jobs/scheduler | No current schedule found in repository; Workstream 0.6 specifies `backend/deployment/payout-maintenance.yaml` with EventBridge Scheduler and ECS/Fargate | Planned; deploy/verify before launch |
| Database state/associations | `Commission`, `Payout`, `PayoutCommission`, `PayoutTransition`, and overloaded `PaymentRecord` exist | Relevant models inspected |
| Notifications | Existing email sender/templates; payout notification outbox, retry, and merchant visibility specified in Workstream 0.6 | Planned; implementation pending |
| Deployment scheduler capability | README and `backend/run-migration.sh` show an AWS ECS/Fargate job pattern; no schedule currently exists | Workstream 0.6 specifies EventBridge Scheduler/Fargate; verify stack inputs before deployment |
