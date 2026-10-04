# Commission-Backed Manual Payouts — Product Design

**Date:** 2026-10-01
**Version:** 1.0
**Status:** Approved by service owner on 2026-10-01; implementation plans created
**Product owner:** Service owner
**Scope:** Commission maturity, affiliate payout requests, merchant approval and manual PayPal recording, payout reporting, and payment notices

## Product summary

Affiliates should request payment against identifiable commissions that have reached the merchant-provided `good_date`, not enter an arbitrary amount against an opaque balance. Merchants need to review the exact commission batch, record an external PayPal payment, and leave an auditable payment record. The service must prevent a commission from being reserved by more than one active payout and must not mark a payout paid until the merchant records the completed transfer.

## Product announcement draft

Affiliates can now request payouts from the specific commissions that are ready, while merchants can verify each sale behind a request before approving it. After a merchant pays an affiliate manually through PayPal, Rosulo records the payment reference and date, updates the payout history, and emails the affiliate a direct link to the payout details. This makes both the request and the payment easier to explain and audit without Rosulo moving funds.

## Problem and evidence

The service currently lacks affiliate selection of specific commission records and a merchant review view that explains the commission batch behind a request. The backend currently accepts a payout currency and reserves all available commissions in that currency; it does not accept commission IDs. The service definition and earlier plans also describe incoming customer `PaymentRecord` ingestion and automatic PayPal execution, which do not match the product owner's intended flow.

Evidence is the service owner's product clarification and review of the current payout/commission code and product documents. No user interviews, analytics baseline, or support-ticket analysis were provided; adoption and operational-impact hypotheses remain unvalidated.

## Goals and success measures

| Goal | Measure / acceptance invariant | Target |
|---|---|---|
| Mature commissions predictably | A commission is promoted only when its merchant-supplied due date has arrived; a missed daily run is caught up on a later run | Promotion occurs on the first successful daily run at or after due time |
| Make requests explainable | Every payout is linked to the exact whole commission rows selected; merchant and affiliate detail totals reconcile to those rows | 100% of payout detail totals and counts reconcile |
| Prevent duplicate reservations | A commission can belong to at most one non-rejected active payout at a time | Zero duplicate active reservations, including concurrent requests |
| Keep settlement auditable | Every payout in `paid` state has exactly one `PayoutPayment` with amount, currency, PayPal reference, payment datetime, and confirming tenant user | 100% of paid payouts have one matching payment record |
| Make payment status visible | A successful manual confirmation produces an affiliate email containing an authenticated payout-detail link | A notification is eventually delivered or visible as retryable failure; payment state is not rolled back by email failure |
| Make merchant payout history useful | Paid totals are available for rolling 12 months and calendar YTD, based on payout payment date and separated by currency | Aggregates reconcile to paid `PayoutPayment` rows |

## Non-goals

- Sending money from Rosulo, holding merchant funds, PayPal API dispatch, PayPal webhooks, or automated payment reconciliation.
- Allowing affiliates to enter payout amounts, partially include a commission, or change a commission amount.
- Implementing refund/chargeback event ingestion or commission reversal behavior in this delivery. A future refund event will use the same external `Event.payment_record_id` as its source sale.
- Adding payment rails beyond manually completed PayPal transfers.
- FX conversion or aggregation across currencies.
- Changing tax policy or treating this product design as tax advice.
- A general in-app notification center.

## Actors and user stories

- **Affiliate:** As an affiliate, I can choose all eligible commissions or a selected set of eligible commission records so that my payout request is traceable to the sales that generated it.
- **Merchant reviewer:** As a merchant user, I can inspect every commission, total, count, and source-sale date range before approval so that I can verify what the affiliate is requesting.
- **Merchant payer:** As a merchant user, I can view the affiliate's payment identity and the amount to transfer, then record the actual PayPal payment time and reference so that the payout is auditable without Rosulo initiating a transfer.
- **Affiliate:** As an affiliate, I receive an email linking to the paid payout details so that I can verify settlement.
- **Merchant operator:** As a merchant user, I can see an affiliate's payout history and paid payout totals for the last 12 months and YTD, separately by currency.
- **Scheduled system process:** As the service, I promote commissions whose due date has arrived without depending on an affiliate opening the payout page.

## Product decisions

### 1. Commission due date and availability

- The merchant owns the business rule that determines `good_date` and sends it on the sale event.
- `good_date` is the commission due date itself. Rosulo does not add a second 14-day hold.
- `good_date` and a nonblank merchant external `payment_record_id` are required on every `sale` event. A sale missing either field fails validation. Rosulo stores `payment_record_id` only on the Event; future refund events use the same tenant-scoped value to identify the source sale.
- The event contract currently models `good_date` as a date. Interpret that date as 00:00 UTC and persist the commission's `available_at` as that UTC instant.
- New commissions start in `pending`. A daily UTC process promotes pending commissions with `available_at <= now` to `available`. It must be idempotent, safe to retry, and catch up after missed runs.
- The daily process does not require an affiliate request and does not send a separate maturity email.

### 2. Affiliate payout request and commission reservation

- An affiliate may request all available commissions for one currency or submit a non-empty list of whole `commission_ids` in one currency.
- An omitted `commission_ids` means all currently available commissions of the required currency. A provided empty list is invalid. There is no amount input.
- Every selected commission must belong to the authenticated affiliate and selected tenant, be `available`, and match the payout currency. Reject the whole request if any item is invalid; do not create a partial payout.
- Derive gross, withholding, and net amounts from the selected commission rows using existing currency/rounding rules.
- Reserve commissions atomically with payout creation. Use a distinct `reserved` commission status for commissions attached to a payout that is pending approval or approved.
- A commission may be in at most one active payout (`pending_approval` or `approved`). Keep the commission association on rejected payouts for history; rejection releases those commissions to `available`, allowing a later request to create a new historical association.
- Existing per-tenant payout eligibility requirements remain in force.

### 3. Merchant review and payout state

- Allowed payout transitions are `pending_approval -> approved | rejected` and `approved -> paid`.
- A merchant reviewer sees the complete payout commission list, source sale date range, commission count, gross, withholding, and net totals before taking action.
- Rejection releases the reserved commissions exactly once and preserves the rejected payout plus its commission links and transition history.
- Approval does not dispatch work to PayPal and does not mark commissions paid. Commissions remain reserved while the merchant performs the transfer outside Rosulo.
- Repeated or concurrent review actions cannot apply an incompatible transition twice.

### 4. Manual PayPal payment and PayoutPayment

- The manual payment UI is PayPal-only for this version. It shows affiliate name, contact email, PayPal recipient identifier, payout amount/currency, and commission count.
- The merchant performs the transfer outside Rosulo, then records the actual payment datetime and PayPal transaction ID/reference. The amount and currency are derived from the approved payout, not entered independently.
- A successful confirmation atomically creates one `PayoutPayment`, marks the payout `paid`, marks its reserved commissions `paid`, and appends the payout transition. An identical retry is idempotent; conflicting payment details return a conflict and do not mutate ledger state.
- `PayoutPayment` is the outgoing affiliate-settlement record and is unique per payout. It records payout ID, amount, currency, payment method (`paypal`), PayPal reference, actual `paid_at`, and confirming tenant user. Do not copy the affiliate's PayPal email into the payment record in v1; show the current profile value in the merchant modal and minimize retained recipient PII.
- Retire the incoming-payment webhook and incoming `PaymentRecord` persistence. A sale event is submitted only after the merchant has confirmed the customer payment and must include the merchant's external `payment_record_id`, stored only on the Event and not as a Rosulo `PaymentRecord` dependency. Future refund events use the same tenant-scoped ID to correlate to the source sale.
- Migrate existing payout-linked payment rows from `payment_records` to `PayoutPayment` without loss. Before removing the incoming-payment model/table, the migration must preserve any existing incoming rows or fail closed for an explicit retention decision; never silently discard them.

### 5. Merchant and affiliate views and notification

- Merchant payout detail shows every included commission and its source sale date, gross, withholding, and net. The total, count, and date range are derived from those rows; the date range uses source sale `Event.occurred_at` in UTC.
- Affiliate payout history links to authenticated payout detail and shows the commissions included, lifecycle status, and PayPal payment details after settlement.
- Merchant affiliate detail/history shows paid payout totals by `PayoutPayment.paid_at`: rolling 12 months and current calendar year-to-date. Report each currency independently and never add mixed currencies together. These are paid payout totals, not lifetime commission-earned totals.
- After the payment transaction commits, send a transactional email with amount/currency and a link to the affiliate's authenticated payout detail. Email failure cannot roll back the payment; delivery must have a retry/recovery path and an observable failure state.

## State model

### Commission

```text
pending --daily maturity job when available_at <= now--> available
available --atomic payout request--> reserved
reserved --payout rejected--> available
reserved --manual payment confirmed on approved payout--> paid
```

`reversed` remains an existing ledger state; implementing refund/chargeback events and reversal timing is explicitly deferred. A commission associated with a rejected payout retains that historical payout link even when its current status returns to `available`.

### Payout

```text
created as pending_approval --> approved --> paid
                     |
                     +-----------> rejected
```

`rejected` and `paid` are terminal in this workflow. Partial payment, cancellation, reopening, and correcting a paid record are not supported by this version; corrections require a separately designed audited workflow.

## Failure and safety requirements

- Missing `good_date`, empty selection, wrong affiliate/tenant, unavailable/reserved/paid commission, duplicate commission ID, unsupported/mixed currency, or ineligible affiliate: reject without creating a payout or changing a commission.
- Two payout requests racing for the same commission: at most one succeeds; the other receives a conflict/no-longer-available response and creates no payout.
- Repeated daily run or process restart: no duplicate transitions or payout associations; next run catches up eligible pending rows.
- Merchant rejection and payment confirmation races: payout row locking/state validation allows only one legal outcome; all related commission and payout changes commit or roll back together.
- Payment reference conflict or a second distinct confirmation: reject without another PayoutPayment or ledger mutation.
- Email failure after commit: keep payout paid, retain a retryable notification failure, and do not send a misleading payment reversal.
- Tenant scoping applies to all merchant queries and mutations; affiliate queries resolve only the authenticated affiliate and selected tenant.

## API and UI contract intent

- Affiliate payout creation accepts `currency` and optional `commission_ids`; the server derives the selected set and totals.
- Merchant payout detail returns payout aggregates plus each linked commission and its source sale/event attributes.
- Merchant payment confirmation accepts `paid_at` and `transfer_reference`; method is fixed to PayPal in this version and the amount is copied from the approved payout.
- Affiliate payout detail returns only the authenticated affiliate's payout and payment information.
- Merchant affiliate reporting returns paid totals by currency for rolling 12 months and YTD.
- Exact route names and schema compatibility are implementation-plan decisions; the product behavior above is the contract.

## Dependencies and risks

| Risk / dependency | Impact | Mitigation |
|---|---|---|
| No daily scheduler is currently deployed for commission maturity | Commissions may remain pending indefinitely if the maintenance task is not scheduled or fails | Deploy and verify the EventBridge Scheduler ECS/Fargate job at 00:15 UTC; retain idempotent catch-up and monitor stopped task failures. |
| Existing `payment_records` table is overloaded by staged W0.2 work | A careless migration could lose payout audit data or historical incoming rows | Copy payout-linked data into `PayoutPayment`; preflight existing rows and fail closed or preserve them before retiring incoming storage. |
| Merchant PayPal recipient identifier may be missing or stale | A merchant may send to the wrong recipient | Block manual payment confirmation until the recipient identifier is present; show it for merchant verification. |
| Email infrastructure may fail after successful payment | Affiliate may not receive notice | Keep payment state authoritative and make email delivery retryable/observable. |
| Refund events are not implemented | Later refunds may affect commissions already requested or paid | Preserve external `payment_record_id`; define refund and post-payment reversal/debt behavior in a separate workflow before enabling refunds. |

## Assumptions and open technical decisions

| # | Assumption / decision | Resolution |
|---|---|---|
| A1 | `good_date` is the merchant-defined due date, not a sale date from which Rosulo adds a hold. | Confirmed by product owner on 2026-10-01. |
| A2 | Date-only `good_date` means 00:00 UTC on that date. | Confirmed by product owner on 2026-10-01. |
| A3 | Every sale event requires merchant `good_date` and external `payment_record_id`; the latter stays on Event for future refund correlation. | Confirmed by product owner on 2026-10-01. |
| A4 | A rejected payout releases commissions for later requests but retains the historical payout link. | Confirmed by product owner on 2026-10-01. |
| A5 | Merchant payout summaries mean completed/paid payouts by payment date, not commission earned. | Confirmed by product owner on 2026-10-01. |
| D1 | What deployment-compatible scheduler runs the due-commission process? | Resolved: EventBridge Scheduler starts a one-shot ECS/Fargate task daily at 00:15 UTC, using the existing Fargate job deployment pattern. The process is idempotent and catches up after missed runs. |
| O2 | If legacy incoming `PaymentRecord` rows exist, what retention/archive policy applies before removing their table? | Migration must detect this; do not discard data. Stop before dropping the table until the service owner resolves retention for any existing rows. |
| D2 | How is payment email delivery retried and observed? | Resolved: create one `PayoutNotification` in the payment transaction, attempt email after commit, expose pending/sending/sent/failed state and a merchant retry action, and have the daily maintenance task recover pending/expired sending rows. SES uses a finite timeout; payment state is never rolled back. |
| D3 | Should the PayPal recipient be copied into the payment record? | Resolved for v1: no recipient snapshot; show the current affiliate profile email in the modal and avoid retaining an extra copy of PII. |

## Related workflow specifications

- `docs/workflows/WORKFLOW-commission-maturity.md`
- `docs/workflows/WORKFLOW-affiliate-payout-request.md`
- `docs/workflows/WORKFLOW-merchant-payout-settlement.md`
- Registry: `docs/workflows/REGISTRY.md`
