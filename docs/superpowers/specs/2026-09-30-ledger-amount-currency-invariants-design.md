# Ledger Amount and Currency Invariants

**Date:** 2026-09-30

**Status:** Implemented; data-conversion verification waived by owner

> **Historical scope note (2026-10-01):** The currency and amount invariants below remain applicable. The sale-event validation contract, availability-date policy, and PaymentRecord model responsibilities are superseded by `docs/superpowers/specs/2026-10-01-commission-backed-manual-payouts-design.md`: every sale requires merchant `good_date` and external `payment_record_id`; `good_date` is the due date (UTC start of day); outgoing settlement uses `PayoutPayment`; incoming payment-record ingestion is retired.

## Goal

Make event, commission, payment-record, payout, and balance amounts deterministic and currency-scoped, while preserving the existing numeric JSON contract for supported clients.

## Agreed implementation order

Complete Workstream 0.5 first, then Workstream 0.3 (per-merchant tax-document eligibility), then return to Workstream 0.2 for the manual merchant-to-affiliate payout flow. Workstream 0.5 does not add PayPal dispatch, change tax rates, implement document review, or change the 14-day payout hold policy.

## Decisions

- **Enabled ledger currencies:** USD, EUR, and BRL. Each has two fractional digits. No FX conversion is performed.
- **Payout currency scope:** A payout request selects one currency and uses commissions in that currency only. No aggregate combines currencies.
- **Provider currency ingestion:** Preserve the provider currency code semantically (normalize it to uppercase) rather than rejecting an event because it is not currently enabled for affiliate processing. For an unsupported currency, store the event, mark its commission generation state as `currency_unsupported`, and do not create a payable commission. Replaying that event after the currency is enabled may create the commission exactly once.
- **Unknown-currency event scale:** Event amounts remain two-decimal values even when the source currency is not enabled, as explicitly selected for this release.
- **Rounding:** Use Decimal arithmetic and `ROUND_HALF_UP` at the currency's minor-unit precision. Keep withholding rates and jurisdiction logic unchanged; qualified tax/accounting support must confirm the withholding rounding treatment before production use.
- **API amounts:** Preserve existing JSON number fields for compatibility. Exact arithmetic and aggregation remain server-side; clients display amounts and do not compute ledger totals.
- **Threshold currency:** A contract `minimum_threshold` is interpreted in the same currency as the event being evaluated.
- **Reversal display:** Lifetime earned is net of signed reversal entries. Pending, available, and paid are separate status buckets. Add `reversal_total` as the positive magnitude of reversed net amounts. Keep the existing `debt` response field as a deprecated alias for compatibility; it does not claim to be a collectible-debt calculation.

## Data model and arithmetic

Use `Decimal` for monetary calculations and SQL `NUMERIC(20,2)` for monetary fields:

- `Event.amount`
- `PaymentRecord.amount`
- `Commission.gross_amount`, `withholding_amount`, and `net_amount`
- `Payout.requested_amount`, `approved_amount`, `withholding_total`, `paypal_fees`, and `net_paid`
- `PayoutCommission.amount`
- `Term.minimum_threshold`

Store `Term.commission_percent` as `NUMERIC(9,6)` and convert contract inputs to Decimal before calculating commissions. The current API field names and numeric JSON representation remain unchanged; Pydantic/API serialization converts at the boundary only. New currency values must be syntactically valid three-letter codes, but event ingestion must not reject a code solely because it is outside the currently enabled ledger currencies.

The `Event` model gains a nullable `commission_status` field. Set it to `currency_unsupported` when a sale cannot yet produce a commission because its currency is not enabled; leave it unset for other event types. Clicks and leads remain non-commissionable. Existing sale processing remains idempotent by tenant-scoped `event_id`.

## Currency-scoped balance and payout behavior

`GET /api/v1/affiliate/balance` and affiliate dashboard balance responses gain `balances_by_currency`, containing one entry per currency with `earned`, `pending`, `available`, `paid`, `tax_retained`, and `reversal_total`. Always return this list. Preserve legacy flat values when exactly one currency is present; when multiple currencies are present, set legacy flat amount fields and `currency` to null rather than returning mixed-currency totals. Preserve the existing signed `reversed` field as a compatibility value; it is the signed sum for the reversed status and is null when currencies are mixed. With no commissions, return an empty list and preserve the existing zero-valued USD legacy shape.

- `earned`: sum of `net_amount` across all commission entries, including signed reversals.
- `pending`, `available`, `paid`: sum `net_amount` within that exact commission status; the buckets are mutually exclusive.
- `tax_retained`: sum the withholding values already recorded on commission entries; do not recalculate tax here.
- `reversal_total`: absolute amount of negative net values in the `reversed` status. This is a reversal metric, not an allocated receivable.

Group affiliate sales-by-sequence and merchant commission-liability dashboard rows by currency as well as their existing dimensions. Affiliate payout requests select a currency and reserve only available commissions matching both affiliate and currency; requests never sum across currencies. Requesting a currency not represented by available commissions returns the existing no-available-commissions error shape.

For sale events whose currency is not enabled, return the accepted event with `commission_status="currency_unsupported"` and no Commission row. A subsequent idempotent retry after currency support is added attempts commission creation again. This makes the held event visible without issuing an incorrectly scaled commission.

## Migration and data safety

The current Alembic head is `c2d3e4f5a6b7`; add the next revision from that head. Convert existing floating-point money columns to `NUMERIC(20,2)` using half-up rounding and commission percentages to `NUMERIC(9,6)`. The migration must preflight null monetary values, unsupported currency values in the active commission/payout ledger, event/commission currency mismatches, and payouts linked to commissions in more than one currency. Abort with a clear error rather than silently guessing in those cases. Event rows may preserve a provider currency outside the current ledger allowlist and are not rejected solely for that reason.

The owner confirmed that the affected financial tables contain no existing rows and waived representative data-conversion reconciliation as not applicable. No migration-test database was created and no Alembic upgrade/downgrade was run in this session. Tests cover supported and unsupported currency event paths; the regular pytest fixture recreates its configured test schema from ORM metadata and does not validate Alembic migrations.

The current `PaymentRecord` remains an incoming customer-payment record during Workstream 0.5. Its existing commission-availability lookup by external payment ID remains unchanged in this workstream and is not a safe production settlement boundary. Workstream 0.2 must replace that lookup with tenant-scoped merchant-to-affiliate payout reconciliation and repurpose the model to include `payout_id`, payment method, and transfer reference.

## Tests

- Decimal commission, withholding, net, payout, and dashboard aggregation examples around half-cent boundaries use `ROUND_HALF_UP`.
- USD, EUR, and BRL balances and dashboard metrics remain separated; no result sums mixed currencies.
- A payout request selects one currency and only includes available commissions of that currency; no payout amount sums commissions across currencies.
- A valid but unsupported provider currency is stored without a commission and exposes `currency_unsupported`; retrying after enabling that currency creates exactly one commission.
- Negative reversal rows retain their signs and contribute to lifetime earned/reversal totals without being folded into pending, available, or paid buckets.
- Migration tests verify representative Float-to-Numeric conversion, null/mixed-currency preflight failures, and preserved per-currency sums on a disposable database.
- Run focused commission, balance/dashboard, event, and payout tests, then the complete backend and frontend suites.

## Out of scope

- Tax-rate or jurisdiction-rule changes, W-9/W-8 review enforcement, and tax-document audit history (Workstream 0.3).
- The 14-day availability policy, repurposing `PaymentRecord`, manual payout confirmation, payout transition history, and disabling the PayPal/SQS transfer path (Workstream 0.2).
- End-to-end refund/chargeback event attribution and commission-reversal creation (separate reversal workflow).
