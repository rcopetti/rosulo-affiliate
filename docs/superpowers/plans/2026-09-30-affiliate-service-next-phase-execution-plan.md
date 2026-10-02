# Rosulo Affiliate Service Next-Phase Execution Plan

> **For agentic workers:** Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` only after the relevant phase has been approved and its scope is separated into an implementation plan. Track work with checkbox (`- [ ]`) syntax.

**Goal:** Turn the current invite-led affiliate MVP into a tenant-safe, financially reliable service with dependable attribution, coherent merchant/affiliate workflows, and measurable program outcomes.

**Architecture:** Keep the existing FastAPI/SQLAlchemy modular monolith and React SPA. First harden the event and commission ledger, tenant boundaries, KYC state, and payout lifecycle; then improve tracking/integration and daily program operations; consider marketplace and broader attribution work only after validating demand. Split each phase into a self-contained implementation plan before coding because the phases touch distinct product and data domains.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, existing SQS infrastructure (not used for manual payout execution), manual PayPal settlement, React, TypeScript, Vite, TanStack Query, Vitest, pytest, httpx.

---

## 1. How to Use This Plan

This is a product-and-engineering execution reference based on a static review of the implementation and repository tests. It describes observed risks, intended outcomes, suggested order, and acceptance gates. It does not claim that the proposed work is implemented or that the current test suite passes.

Do not execute all phases as one change. Before each phase, confirm business decisions, inspect current code and migrations, and create a smaller implementation plan with exact migration names, test cases, and task sequencing. Keep this file as the roadmap; update the checkboxes and phase status when work is approved and completed.

### Priority definitions

- **P0 — Before real-money or broader multi-tenant production use:** tenant isolation, payout idempotency/reconciliation, coherent payout eligibility, and trustworthy financial records.
- **P1 — Next implementation cycles:** reliable tracking integration, partner lifecycle controls, and usable reporting.
- **P2 — Validate demand first:** partner marketplace/discovery, deeper attribution, additional rails/currencies, and other scale-oriented capabilities.

The P0 items are launch gates, not a claim that every item is already a known production incident.

## 2. Current Capability Baseline

The repository currently implements merchant invitations, per-affiliate commission contracts, affiliate-created campaigns, click/lead/sale event ingestion, a commission ledger, affiliate payout requests, merchant approval/rejection, manual merchant-confirmed settlement foundation from W0.2, and basic dashboards. It does not yet implement the new product requirement for selected commission batches, scheduled due-date maturity, itemized merchant review, PayPal recipient instructions, payout-specific payment storage, or paid-payout notices/reporting.

Relevant implementation entry points include:

- Merchant invitation, affiliate records, and KYC approval: `backend/app/api/v1/admin/affiliates.py`, `backend/app/services/affiliate.py`, `backend/app/services/affiliate_invite.py`.
- Contract rules: `backend/app/api/v1/admin/contracts.py`, `backend/app/services/contract.py`, `backend/app/services/commission.py`.
- Campaign and event ingestion: `backend/app/api/v1/affiliate/campaigns.py`, `backend/app/services/campaign.py`, `backend/app/api/v1/public/events.py`, `backend/app/services/event.py`.
- Payout lifecycle: `backend/app/api/v1/affiliate/payouts.py`, `backend/app/api/v1/admin/payouts.py`, `backend/app/services/payout.py`, `backend/app/db/models.py`.
- Email delivery: `backend/app/services/email.py` and templates; payout notice workflow is not implemented.
- Reporting and portals: `backend/app/services/dashboard.py`, `frontend/src/pages/admin/`, `frontend/src/pages/affiliate/`.

### Review findings that drive this plan

1. Event idempotency lookup was globally unique and unscoped; W0.1 now scopes the event ID uniqueness and lookup by tenant.
2. W0.2 disables automatic PayPal dispatch and records merchant-confirmed manual settlements. The remaining product gap is the selected-commission batch lifecycle and itemized merchant verification; the active implementation still accepts only a currency and reserves all eligible commissions.
3. Merchant-side KYC approval and the affiliate UI previously used separate approval signals; W0.3 now unifies per-merchant document review and payout eligibility.
4. The integration UI advertises a browser click endpoint at `/api/v1/tracking/track-click`, but that route is not registered in the backend. Merchants are instructed to build their own proxy.
5. The authenticated affiliate join route can create a tenant association directly without the invitation path or a contract.
6. The affiliate dashboard accepts a campaign selection in the UI but the API route does not pass the filter through. The dashboard's `earned` total is initialized but not calculated from the implemented commission statuses.
7. Payment/event schemas support currency labels, but currency-scope gaps existed; W0.5 defines Decimal/Numeric storage and currency-scoped balances. Verify current branch implementation before relying on this baseline.
8. Sale events include an external `payment_record_id`; the current incoming-payment webhook/storage and future refund-to-sale reversal workflow must be reconciled with the approved product design.

## 3. Before Starting Any P0 Implementation

The following payout product decisions were confirmed by the service owner on 2026-10-01 and are authoritative for follow-up implementation planning:

- **Payout funding model:** Manual merchant-funded settlement. Merchants transfer funds outside Rosulo; Rosulo records the actual payment datetime, PayPal reference, and confirming tenant user. Rosulo does not dispatch PayPal/SQS payouts or assume platform payout liability.
- **Sale event contract:** The merchant sends a sale only after payment confirmation and supplies both `good_date` and external `payment_record_id`. `good_date` is required, is the due date itself, and is interpreted as 00:00 UTC. Rosulo adds no additional 14-day hold and promotes due commissions in a daily UTC process; future refunds use the same external ID.
- **Payout selection:** Affiliate requests all available commissions of one currency or selected whole commission IDs; no arbitrary amount. Rejected commissions may be requested again, while the prior payout association remains in audit history.
- **Manual payment:** PayPal only for v1. The merchant sees affiliate identity, contact email, PayPal recipient identifier, payout amount/currency, and commission count, then records `paid_at` and the PayPal transaction/reference.
- **Payment data model:** Use `PayoutPayment` for outgoing affiliate settlement. Retire incoming payment-record ingestion/storage; retain `Event.payment_record_id` as the merchant's external sale/refund correlation identifier. Migrate payout-linked legacy rows and never silently discard any historical incoming rows.
- **Paid notice and reporting:** Email the affiliate a link to authenticated payout detail after payment commit. Merchant affiliate summaries show paid payout totals by payment date for rolling 12 months and calendar YTD, separately per currency.

Other open finance decisions remain: currency support stays currency-scoped with no FX conversion; tax and withholding behavior must receive qualified tax/accounting review; commission base and fee allocation must be resolved before changing those policies; click attribution rules remain under Workstream 1.1. The detailed payout design is `docs/superpowers/specs/2026-10-01-commission-backed-manual-payouts-design.md`.

## 4. P0 — Trust, Tenant Isolation, and Financial Correctness

### Workstream 0.1: Scope event idempotency to tenant

**Status:** Complete (2026-09-30; migration upgrade/downgrade verified with isolated synthetic fixtures).

**Outcome:** Retrying an event in the same tenant is idempotent; an identical event ID used by another tenant cannot return or modify the first tenant's event.

**Likely files:**
- Modify: `backend/app/db/models.py`
- Create: next Alembic revision under `backend/alembic/versions/`
- Modify: `backend/app/services/event.py`
- Test: `backend/tests/test_events.py`, `backend/tests/test_tracking.py`

**Implementation sequence:**

- [x] Add a failing API test that ingests one event for tenant A, then submits the same `event_id` under tenant B; assert tenant B receives only its own tenant-scoped result and tenant A's event details are not returned.
- [x] Add/adjust a same-tenant retry test; assert it returns the original event and does not create an additional commission for a repeated sale.
- [x] Replace global event-ID uniqueness with a database uniqueness constraint on `(tenant_id, event_id)` and scope the service lookup to both fields. Create the Alembic migration using the repository's current migration head.
- [x] Run the event/tracking tests, then the complete backend suite.

**Acceptance criteria:**

- [x] Same-tenant retry returns the original event and remains commission-idempotent.
- [x] Another tenant may use the same external event ID without seeing the first tenant's event.
- [x] A database constraint, not only application logic, enforces the new uniqueness boundary.
- [x] Migration upgrade and downgrade behavior is reviewed against representative isolated event fixtures.

### Workstream 0.2: Make payout execution idempotent and reconcilable

**Status:** Complete (2026-10-01; manual merchant-funded settlement selected; migration upgrade/downgrade and legacy-row preservation verified on a disposable PostgreSQL database).

**Outcome:** A payout is not marked paid until a merchant user records the completed external transfer. Duplicate requests and stale queue messages cannot create another transfer, and commissions stay reserved until the merchant confirms payment or rejects the payout.

**Likely files:**
- Modify: `backend/app/db/models.py`, `backend/app/services/payout.py`, `backend/app/services/commission.py`, `backend/app/services/balance.py`
- Modify: `backend/app/api/v1/admin/payouts.py`, `backend/app/api/v1/public/webhooks.py`
- Modify: `backend/app/queue/handlers.py`
- Modify: `backend/app/schemas/payout.py`
- Modify: `frontend/src/api/admin/payouts.ts`, `frontend/src/api/types.ts`, `frontend/src/components/admin/PayoutQueue.tsx`, `frontend/src/components/admin/PayoutDetail.tsx`, `frontend/src/components/affiliate/PayoutsTable.tsx`, `frontend/src/pages/admin/PayoutsPage.tsx`, `frontend/src/pages/admin/DashboardPage.tsx`
- Create: `backend/alembic/versions/b1c2d3e4f5a6_manual_payout_settlement.py`
- Test: `backend/tests/test_payout.py`, `backend/tests/test_document_review_migration.py`, `frontend/src/tests/components/PayoutQueue.test.tsx`, `frontend/src/tests/components/PayoutsTable.test.tsx`

**Implementation sequence:**

- [x] Write failing tests for concurrent duplicate payout requests, duplicate approval/rejection, stale worker redelivery, explicit payment confirmation, duplicate/conflicting confirmation, rejection release, and commissions before/after the 14-day availability hold. Assert that an unconfirmed approved payout remains unpaid and its commissions remain reserved.
- [x] Define and enforce the permitted transitions: `pending_approval -> approved | rejected`; `approved -> paid` only through merchant payment confirmation. Record each transition's sequence, actor, and time.
- [x] Add a payout-linked payment record with payment method, transfer reference, amount, currency, and confirming tenant user. Preserve legacy incoming payment records and migrate existing payouts with an actor-less baseline history entry.
- [x] Disable PayPal payout webhook handling and automatic PayPal dispatch. The PayPal webhook returns `410`; the worker safely no-ops old payout messages, and approval no longer publishes payout messages to SQS.
- [x] Keep commissions reserved after approval. A merchant's explicit confirmation creates one payment record and marks the payout and commissions paid atomically; an identical retry is idempotent and conflicting payment details are rejected. Show the recorded method/reference in the affiliate payout history.
- [x] Make payout creation and commission reservation atomic with commission row locks; prove concurrent requests reserve the available commission set only once.
- [x] Remove queue publication from the manual payout approval transaction; no outbox is needed when approval does not enqueue a transfer.
- [x] Record the confirmed manual merchant-funded model in Section 3. No platform-held payout funds, merchant payout credentials, or automated provider settlement are introduced.

**Acceptance criteria:**

- An approved payout and its commissions remain reserved until a merchant user records the external payment; no automatic provider failure path releases commissions.
- Duplicate queue delivery, payout requests, approvals, rejections, and identical payment confirmations cannot duplicate settlement or ledger changes.
- Every payout has ordered, auditable transition history; a completed payout has one tenant-scoped payment record with amount, currency, payment method, transfer reference, and confirming user.
- Rejected payouts return their commissions to an eligible balance exactly once; completed payouts do not.
- Stored payout amount, currency, withholding, net amount, manual payment record, and affiliate-visible paid state reconcile.

**Product follow-up note (2026-10-01):** W0.2 is complete as the manual settlement/idempotency foundation. It did not deliver selected commission batches, daily `good_date` maturity, merchant itemized commission review, PayPal recipient instructions, payout-specific `PayoutPayment`, paid payout reporting, or affiliate payment email. Its current overloaded `PaymentRecord` implementation is transitional; Workstream 0.6 supersedes the model responsibility without changing W0.2's historical completion record.

### Workstream 0.3: Unify KYC/document review and payout eligibility

**Outcome:** Merchant review, document status, and affiliate payout eligibility use one explicit, auditable source of truth.

**Status:** Complete (2026-10-01; live Alembic upgrade/downgrade verification was skipped at the owner's direction; revision-chain and offline SQL generation checks passed).

**Likely files:**
- Modify: `backend/app/db/models.py`, `backend/app/services/affiliate.py`, `backend/app/services/affiliate_account.py`, `backend/app/services/payout.py`, `backend/app/services/document_review.py`
- Modify: `backend/app/api/v1/admin/affiliates.py`, `backend/app/api/v1/affiliate/profile.py`, `backend/app/api/v1/affiliate/merchants.py`, `backend/app/api/v1/dependencies.py`
- Modify: `backend/app/schemas/affiliate.py`, `backend/app/schemas/affiliate_account.py`; create `backend/app/schemas/document_review.py`
- Modify: `frontend/src/api/admin/affiliates.ts`, `frontend/src/api/affiliate/profile.ts`, `frontend/src/api/types.ts`
- Modify: `frontend/src/pages/admin/AffiliateDetailPage.tsx`, `frontend/src/pages/admin/AffiliatesPage.tsx`, `frontend/src/pages/admin/DashboardPage.tsx`, `frontend/src/pages/affiliate/ProfilePage.tsx`, `frontend/src/pages/affiliate/RequestPayoutPage.tsx`, `frontend/src/components/affiliate/KycUploader.tsx`, `frontend/src/components/shared/KycStatusBadge.tsx`
- Create: `backend/alembic/versions/a9b0c1d2e3f4_affiliate_document_review.py`
- Test: `backend/tests/test_document_review.py`, `backend/tests/test_document_review_migration.py`, `backend/tests/test_payout.py`; `frontend/src/tests/components/KycUploader.test.tsx`, `frontend/src/tests/pages/AffiliateDetailPage.test.tsx`, `frontend/src/tests/pages/RequestPayoutPage.test.tsx`

**Implementation sequence:**

- [x] Add failing API/UI tests covering no documents, a pending document, an approved document, a rejected document, and per-merchant eligibility.
- [x] Define per-merchant document copies. Store append-only review decisions with reviewer, decision time, and rejection reason; preserve legacy account-wide documents without using their booleans for eligibility.
- [x] Update merchant review actions and affiliate status rendering to read/write the same policy state.
- [x] Enforce payout eligibility in the backend from that policy state; make the frontend display the backend's decision and reason rather than implementing a different rule.
- [x] Align accepted upload types and document requirements with the actual merchant policy. Describe this as tax-document review, not general identity/business verification.

**Acceptance criteria:**

- [x] Merchant and affiliate views show consistent document and payout eligibility states.
- [x] The backend rejects ineligible payout requests even when called outside the UI.
- [x] Review actions are attributable and rejection reasons are visible to the intended users.
- [x] Re-uploading a new document does not erase or misrepresent prior review history.

### Workstream 0.4: Enforce onboarding and merchant-role boundaries

**Outcome:** A tenant-affiliate association is created through an explicitly authorized onboarding state and has valid commission terms before it can track payable activity.

**Likely files:**
- Modify: `backend/app/api/v1/affiliate/merchants.py`, `backend/app/api/v1/dependencies.py`
- Modify: `backend/app/services/affiliate_invite.py`, `backend/app/services/affiliate_account.py`
- Modify: `backend/app/api/v1/admin/affiliates.py`, `backend/app/api/v1/admin/contracts.py`
- Modify: `frontend/src/api/auth.ts`, `frontend/src/pages/affiliate/MerchantSelectPage.tsx`
- Test: `backend/tests/test_affiliate.py`, `backend/tests/test_auth.py`, and a focused frontend merchant-selection test

**Implementation sequence:**

- [ ] Add failing tests proving a known tenant ID cannot be used to bypass the intended invitation or application workflow.
- [ ] Remove direct self-join or convert it to an application that remains pending until merchant approval. Ensure any path that activates an affiliate creates/accepts valid terms before payable events can be credited.
- [ ] Enforce tenant-user roles on merchant administration endpoints. Decide which roles can invite, edit contracts, approve KYC, rotate API keys, and approve payouts; then add positive and negative authorization tests.
- [ ] Align the merchant-list API response shape with the frontend `Tenant` type and selector (`id`, `name`). Add a test for accounts linked to more than one merchant.

**Acceptance criteria:**

- No unapproved self-join creates an active affiliate record.
- Every active affiliate relationship has valid contract terms or is explicitly non-commissionable with a visible state.
- Least-privilege role checks apply to sensitive merchant actions.
- Affiliates can select each tenant returned by the API without shape mismatch.

### Workstream 0.5: Define ledger amount and currency invariants

**Outcome:** Every balance is mathematically sound and does not add values across currencies or rely on binary floating-point for money.

**Likely files:**
- Modify: `backend/app/db/models.py`, schemas under `backend/app/schemas/`, calculation/services under `backend/app/services/`
- Create: next Alembic revision under `backend/alembic/versions/`
- Modify: `frontend/src/api/types.ts`, `frontend/src/lib/formatters.ts` and affected balance/payout components
- Test: `backend/tests/test_commission.py`, `backend/tests/test_payout.py`, `backend/tests/test_dashboard.py`, frontend balance/formatting tests

**Implementation sequence:**

- [x] Add failing tests for rounding, fractional commission calculations, negative reversals, and attempts to combine different currencies.
- [x] Choose a decimal representation with explicit currency precision and migrate financial columns to Numeric. The user confirmed the existing tables are empty, so data conversion/reconciliation verification was waived as not applicable; no migration upgrade/downgrade was run in this session.
- [x] Keep every aggregate and payout request currency-scoped; store valid provider currencies outside the ledger allowlist without generating payable commissions.
- [x] Define balance semantics in API schemas: distinguish lifetime earned (net of reversals) from mutually exclusive pending, available, and paid buckets; expose reversal totals.
- [x] Test the definitions against commission and payout records rather than presenting status labels as interchangeable totals.

**Acceptance criteria:**

- No aggregate includes amounts from different currencies.
- Rounding rules are deterministic and covered by tests.
- Affiliate and merchant balance views reconcile to the same ledger.
- Status totals, reversal totals, and lifetime earned have documented, non-overlapping meanings.

### Workstream 0.6: Complete the commission-backed manual payout product

**Status:** Product design approved and detailed implementation plans ready (2026-10-01); implementation not started.

**Outcome:** Affiliates request payment for all or selected available whole commission rows; merchants inspect the complete batch, approve/reject it, manually pay through PayPal, record actual payment details, and affiliates receive a payout-detail email. Daily maturity follows the merchant-provided due date.

**Authoritative product/workflow documents:**
- Product design: `docs/superpowers/specs/2026-10-01-commission-backed-manual-payouts-design.md`
- Workflow registry: `docs/workflows/REGISTRY.md`
- Workflow specs: `docs/workflows/WORKFLOW-commission-maturity.md`, `docs/workflows/WORKFLOW-affiliate-payout-request.md`, `docs/workflows/WORKFLOW-merchant-payout-settlement.md`

**Delivery split:** Execute these two dependent implementation plans in order after confirming the prerequisite W0.2 code is committed and the deployment target is configured:

1. `docs/superpowers/plans/2026-10-01-commission-availability-and-request-implementation-plan.md` — require `good_date` on sale events; set `available_at` to 00:00 UTC on that date; add a daily idempotent catch-up process; support all/selected whole commission IDs; separate `pending`, `available`, and `reserved`; atomically reserve only valid same-currency commissions; retain rejected payout links while releasing their commissions.
2. `docs/superpowers/plans/2026-10-01-merchant-manual-payout-operations-implementation-plan.md` — itemized merchant review, affiliate payout detail/history, manual PayPal instructions and confirmation, `PayoutPayment`, paid payout summaries (rolling 12 months and YTD by payment date/currency), affiliate email delivery/retries, incoming-payment ingestion retirement, and safe legacy-data migration.

**Dependencies and implementation gates:** W0.2 settlement foundation, W0.3 payout eligibility, and W0.5 amount/currency invariants. The scheduler decision is resolved: EventBridge Scheduler launches an ECS/Fargate maintenance task daily at 00:15 UTC using the existing one-shot Fargate deployment pattern; verify it in a non-production environment. Payment notices use a transactional `PayoutNotification`, after-commit send, visible status/retry action, and daily recovery of pending/expired-send rows. Migration copies payout-linked rows and aborts before dropping `payment_records` if any historical incoming rows need an owner-approved retention/archive decision; no silent data deletion. Refund ingestion remains a separate workflow, with the sale event's external `payment_record_id` retained for future correlation.

**Acceptance criteria:**

- Every sale event requires merchant-supplied `good_date` and external `payment_record_id`; no extra 14-day hold is applied.
- Due commissions become `available` through the daily process, even if the job missed prior runs; repeated/concurrent runs do not duplicate transitions.
- A payout contains all or selected whole commissions in one currency, derives its totals from those rows, and cannot concurrently reserve one commission twice.
- Merchant review exposes every linked commission, source sale date range, count, gross, withholding, and net before approval/rejection.
- Rejection releases commissions once and retains historical association; approval retains reservation.
- A payout reaches `paid` only with one `PayoutPayment` containing actual merchant-entered payment time/reference; no PayPal API dispatch occurs.
- Merchant paid payout history and rolling 12-month/YTD summaries reconcile to payment records per currency.
- The affiliate receives a retryable transactional email linking to authenticated payout details; delivery failure cannot reverse payment.
- Incoming-payment webhook/storage is retired safely; the sale event's external `payment_record_id` remains available for future refund correlation.

## 5. P1 — Make Tracking and Reporting Dependable

### Workstream 1.1: Ship a supported click-to-conversion integration

**Outcome:** A merchant can integrate link clicks and server-confirmed conversions using supported Rosulo endpoints or maintained SDKs, without inventing a missing endpoint.

**Likely files:**
- Modify: `backend/app/api/v1/__init__.py`, `backend/app/api/v1/public/`, `backend/app/services/event.py`
- Modify: `backend/app/schemas/event.py`, `backend/app/api/v1/admin/integrations.py`
- Modify: `frontend/src/pages/admin/IntegrationPage.tsx`
- Create: tracking integration tests and a versioned integration guide under `docs/`

**Implementation sequence:**

- [ ] Add an API contract test for each advertised click, lead, sale, refund, and chargeback path before publishing instructions.
- [ ] Choose a supported pattern: a Rosulo-hosted first-party redirect/click endpoint, a documented merchant-side proxy backed by working API examples, or both. Do not show a snippet that calls a nonexistent endpoint.
- [ ] Specify and test link/code parsing, click ID persistence, configured lookback window, attribution precedence, repeat customer handling, and event retry/idempotency semantics.
- [ ] Add explicit `coupon_code` and UTM support only after the attribution precedence is approved; preserve server-side conversion confirmation and never expose tenant API keys in browser code.
- [ ] Add webhook or postback delivery for relevant downstream event/status changes with signatures, retry policy, and merchant-visible delivery logs if merchants need outbound notifications.
- [ ] Make the allowed-domain configuration enforceable by the endpoint that uses it, or remove the misleading configuration and explain the actual trust boundary.

**Acceptance criteria:**

- Every integration example runs against the API contract tests.
- A click can be tied to a later lead and paid sale according to a documented attribution policy.
- Client integration cannot expose a merchant API secret.
- Unsupported event types and invalid campaign/click/lead references fail clearly and do not create payable commissions.

### Workstream 1.2: Correct dashboard metrics and filters

**Outcome:** Merchant and affiliate dashboards show consistent, filterable, decision-useful data.

**Likely files:**
- Modify: `backend/app/api/v1/affiliate/dashboard.py`, `backend/app/services/dashboard.py`, `backend/app/schemas/dashboard.py`
- Modify: `frontend/src/api/affiliate/dashboard.ts`, `frontend/src/pages/affiliate/DashboardPage.tsx`
- Modify: `frontend/src/pages/admin/DashboardPage.tsx`, reporting components under `frontend/src/components/admin/` and `frontend/src/components/affiliate/`
- Test: `backend/tests/test_dashboard.py`, frontend dashboard tests

**Implementation sequence:**

- [ ] Add tests proving campaign selection filters every metric it claims to filter and does not change unrelated account-wide balances.
- [ ] Pass and validate `campaign_id` through the affiliate route; apply it consistently to lead and commission/sales metrics or remove the filter until all visible metrics support it.
- [ ] Implement the documented earned/balance definitions from Workstream 0.5 and return explicit currency-scoped values.
- [ ] Define the merchant's core measures: clicks, leads, attributed paid sales, gross revenue, commission liability, conversion rate, reversal totals, and payout aging. Use provider/payment status as the source of truth for paid sales.
- [ ] Add date-range filters, pagination where result sets can grow, and CSV export for event, affiliate, commission, and payout reports.
- [ ] Add reconciliation tests that compare dashboard aggregates with fixture ledger rows.

**Acceptance criteria:**

- UI filters are honored server-side and tested.
- Dashboard totals reconcile to underlying rows and clearly label revenue versus commission amounts.
- Date ranges, currencies, and event/payment statuses are visible in the report contract.
- Large tables can be navigated without loading unbounded records.

## 6. P1 — Improve Merchant and Affiliate Program Operations

### Workstream 2.1: Complete partner lifecycle management

**Outcome:** Merchants can recruit, assess, approve, enable, pause, and offboard affiliates with an explicit status and communication history.

**Likely files:**
- Modify: `backend/app/db/models.py`, `backend/app/services/affiliate_invite.py`, `backend/app/services/affiliate.py`
- Modify: `backend/app/api/v1/admin/affiliates.py`, related schemas under `backend/app/schemas/`
- Modify: `frontend/src/pages/admin/AffiliatesPage.tsx`, `frontend/src/pages/admin/AffiliateDetailPage.tsx`, invite/create components
- Create: migration and workflow tests under `backend/tests/`

**Implementation sequence:**

- [ ] Add invitation lifecycle tests for pending, accepted, expired, revoked, resent, and duplicate-email cases.
- [ ] Implement merchant actions to list pending invites, resend/revoke them, and see delivery/acceptance state.
- [ ] Define affiliate relationship statuses (for example: invited, pending review, active, paused, rejected, terminated) and allowed transitions; store actor, timestamp, and reason for sensitive transitions.
- [ ] Add merchant review/application workflow only if open applications are part of the chosen recruitment model. Keep invitation-only mode as a supported setting if that remains the target customer model.
- [ ] Make campaign creation and payable event attribution respect the affiliate relationship status.
- [ ] Provide clear affiliate-facing status, next required action, and support path.

**Acceptance criteria:**

- Each lifecycle status has a tested transition policy and is enforced by the API.
- Paused, rejected, or terminated affiliates cannot generate payable commissions under a new click/sale unless an explicit policy allows it.
- Merchants can recover from email delivery failure without creating duplicate identities or contracts.

### Workstream 2.2: Improve commission program controls and partner enablement

**Outcome:** Merchants can operate the commission models their target programs need, and affiliates have the material and guidance to promote effectively.

**Likely files:**
- Modify: `backend/app/db/models.py`, `backend/app/services/contract.py`, `backend/app/services/commission.py`
- Modify: `backend/app/schemas/contract.py`, `backend/app/api/v1/admin/contracts.py`
- Modify: `frontend/src/pages/admin/ContractEditPage.tsx`, `frontend/src/pages/affiliate/CampaignsPage.tsx`, affiliate layout/pages as needed
- Create: focused contract and commission tests

**Implementation sequence:**

- [ ] Interview current merchants and affiliates or review support/operational data to identify the top unmet commission and enablement needs before expanding scope.
- [ ] Preserve immutable contract history: changes to future terms must not retroactively alter commissions already calculated under prior terms.
- [ ] Based on validated demand, add one commission model at a time (for example flat CPA, recurring revenue share, partner group rules, caps, or performance bonuses); write deterministic test cases for precedence and effective dates first.
- [ ] Add a merchant-managed resource library for approved links, copy, product assets, and program rules if partner enablement is a confirmed activation barrier.
- [ ] Include affiliate education on material-connection disclosures and merchant program policy. Treat it as operational guidance, not legal certification.

**Acceptance criteria:**

- Existing approved commissions retain the terms and calculation basis that produced them.
- New commission models have documented precedence, effective dates, reversal handling, and payout behavior.
- Any partner-facing marketing material is versioned or attributable to its merchant/program owner.

## 7. P2 — Expansion Bets (Validate Before Scheduling)

Do not build these as prerequisites for a reliable invite-led program. Promote an item only when customer evidence, sales demand, and engineering capacity justify it.

- **Partner discovery/marketplace:** test whether merchants lack enough recruiting reach and whether affiliates want cross-program discovery. A public marketplace adds trust, moderation, matching, and fraud operations.
- **Ready-made commerce/CRM integrations:** prioritize the integrations most frequently requested by qualified customers; measure setup completion and support burden for each.
- **Advanced attribution:** cross-device, multi-touch, view-through, and advanced identity resolution require a clear privacy and consent policy and a validated demand case.
- **Fraud/risk tooling:** begin with deterministic detection and review queues (duplicate customers, suspicious click/conversion ratios, rapid repeated conversions) before considering scoring models. Provide a dispute and audit path.
- **Additional payout rails and currencies:** implement only after the funding model, currency ledger, tax responsibilities, reconciliation, and provider support are agreed.
- **White-labeling, mobile applications, and partner ecosystem motions beyond affiliates:** defer until the core program has demonstrable usage and retention.

## 8. Success Measures and Phase Gates

Establish a baseline before setting numeric targets. Assign one product owner and one engineering DRI to each approved workstream during planning.

| Measure | Definition | Phase gate |
|---|---|---|
| Tenant-safe event idempotency | Duplicate requests within one tenant do not duplicate events/commissions; cross-tenant IDs never expose another tenant's row | P0 tenant-isolation tests pass |
| Payout reconciliation | Every payout reaches an auditable merchant-confirmed terminal state with exactly one matching `PayoutPayment` or remains visibly actionable | P0 manual-settlement workflow tests and migration checks pass |
| Ledger accuracy | Dashboard, affiliate balance, selected payout commissions, and `PayoutPayment` reconcile by currency | P0 ledger examples reconcile exactly under documented rounding |
| Tracking coverage | Share of merchant-confirmed paid conversions with valid click/lead/campaign attribution | P1 integration telemetry is available and validated |
| Partner activation | Invited affiliates who complete profile/required documents, create a campaign, and generate a first valid conversion | P1 funnel events and baseline are collected |
| Program efficiency | Time from payout request to confirmed payment; merchant review time; integration setup completion time | Baselines and ownership are agreed before target-setting |
| Support quality | Volume of disputes about missing attribution, commission calculation, KYC state, and late/missing payouts | Track reason-coded cases and review each release cycle |

**Release gates:**

- Do not expand real-money payout volume until tenant-scoped idempotency, payout reconciliation, and ledger tests pass.
- Do not advertise direct browser tracking until the route/SDK and its security controls are implemented and tested.
- Do not enable additional tax jurisdictions until the tax rules and responsibilities receive qualified review.
- Do not claim multi-currency balances until all ledger, aggregation, and payout paths preserve currency boundaries.

## 9. Verification Commands

Run backend commands from `backend/` and frontend commands from `frontend/`:

```bash
uv run pytest tests/ -v
npm run test
npm run build
npm run lint
npm run e2e
```

The backend test fixture creates and drops tables in a dedicated test database and may create a database named with a `_test` suffix. Read `backend/tests/conftest.py` and configure `TEST_DATABASE_URL` to a disposable test database before running tests. E2E tests require a running backend as described in `README.md`.

For migration work, additionally verify `uv run alembic upgrade head` against a disposable database with representative pre-migration data, then test downgrade/restore behavior where rollback is supported. Never run destructive migration verification against production data.

## 10. Market References

These sources are vendor-published feature descriptions and should be treated as directional product benchmarks, not neutral certification criteria:

- PartnerStack, [partner tracking](https://partnerstack.com/platform/partner-tracking) and [partner commissions](https://partnerstack.com/platform/partner-commissions): partner-specific/custom links, UTM support, integrations, flexible commission triggers, payout automation, reporting, and fraud controls.
- impact.com, [affiliate marketing platform](https://impact.com/affiliate-marketing/): partner discovery, cross-device/comprehensive tracking, workflows, reporting, and fraud protection.
- U.S. FTC, [Endorsement Guides: frequently asked questions](https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking): affiliate relationships and disclosure guidance. Product reminders and policies should not be represented as legal advice or a compliance guarantee.
