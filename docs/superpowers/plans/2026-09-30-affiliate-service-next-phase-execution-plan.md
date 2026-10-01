# Rosulo Affiliate Service Next-Phase Execution Plan

> **For agentic workers:** Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` only after the relevant phase has been approved and its scope is separated into an implementation plan. Track work with checkbox (`- [ ]`) syntax.

**Goal:** Turn the current invite-led affiliate MVP into a tenant-safe, financially reliable service with dependable attribution, coherent merchant/affiliate workflows, and measurable program outcomes.

**Architecture:** Keep the existing FastAPI/SQLAlchemy modular monolith and React SPA. First harden the event and commission ledger, tenant boundaries, KYC state, and payout lifecycle; then improve tracking/integration and daily program operations; consider marketplace and broader attribution work only after validating demand. Split each phase into a self-contained implementation plan before coding because the phases touch distinct product and data domains.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, SQS, PayPal integration, React, TypeScript, Vite, TanStack Query, Vitest, pytest, httpx.

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

The repository currently implements merchant invitations, per-affiliate commission contracts, affiliate-created campaigns, click/lead/sale event ingestion, a commission ledger, affiliate payout requests, merchant approval/rejection, PayPal dispatch through a worker, and basic merchant and affiliate dashboards. The product is therefore a useful foundation for a narrow, invite-led affiliate program.

Relevant implementation entry points include:

- Merchant invitation, affiliate records, and KYC approval: `backend/app/api/v1/admin/affiliates.py`, `backend/app/services/affiliate.py`, `backend/app/services/affiliate_invite.py`.
- Contract rules: `backend/app/api/v1/admin/contracts.py`, `backend/app/services/contract.py`, `backend/app/services/commission.py`.
- Campaign and event ingestion: `backend/app/api/v1/affiliate/campaigns.py`, `backend/app/services/campaign.py`, `backend/app/api/v1/public/events.py`, `backend/app/services/event.py`.
- Payout lifecycle: `backend/app/api/v1/affiliate/payouts.py`, `backend/app/api/v1/admin/payouts.py`, `backend/app/services/payout.py`, `backend/app/queue/handlers.py`, `backend/app/integrations/paypal.py`.
- Reporting and portals: `backend/app/services/dashboard.py`, `frontend/src/pages/admin/`, `frontend/src/pages/affiliate/`.

### Review findings that drive this plan

1. Event idempotency lookup uses a globally unique `event_id` without scoping the lookup to the authenticated tenant. The response can therefore return another tenant's existing event when IDs collide.
2. Payout dispatch does not yet form a reliable provider-confirmed state machine: the PayPal webhook is a stub, the payout batch ID is hard-coded, a successful API response is treated as paid, and exceptions release commissions even when provider outcome may be ambiguous.
3. Merchant-side KYC approval and the affiliate UI use separate approval signals. The merchant approval path changes the affiliate-level flag; the affiliate payout page checks each uploaded document's `approved` flag.
4. The integration UI advertises a browser click endpoint at `/api/v1/tracking/track-click`, but that route is not registered in the backend. Merchants are instructed to build their own proxy.
5. The authenticated affiliate join route can create a tenant association directly without the invitation path or a contract.
6. The affiliate dashboard accepts a campaign selection in the UI but the API route does not pass the filter through. The dashboard's `earned` total is initialized but not calculated from the implemented commission statuses.
7. Payment/event schemas support currency labels, but some balance and payout paths assume USD. Amounts use floating-point database columns. Currency scope and money representation need to be decided before expanding payment support.
8. The service definition describes refund/chargeback reversals, but the accepted event types and payment webhook do not implement an end-to-end reversal workflow.

## 3. Before Starting Any P0 Implementation

Resolve these product and finance decisions with the service owner before changing payout or tax behavior:

- **Payout funding model:** Does each merchant fund its own affiliate payouts, or does Rosulo pay from a platform-controlled account and settle with merchants separately? The current PayPal integration uses application-level credentials. Do not design merchant onboarding, credential storage, or liability accounting until this ownership model is explicit.
- **Currency policy:** Is the next release USD-only, or must merchants and affiliates transact in multiple currencies? Until multi-currency balances and payouts are designed, either explicitly reject unsupported currencies or implement per-currency accounting; do not sum mixed currencies into one balance.
- **Tax/compliance scope:** Confirm supported jurisdictions and withholding behavior with qualified tax counsel/accounting support. The existing fixed withholding calculation is not a jurisdiction-aware tax rules engine and this plan does not treat it as tax advice.
- **Attribution policy:** Decide the initial click lookback window, precedence between click/lead/coupon/manual attribution, and behavior for repeat conversions before productizing a browser SDK.

Record the decisions in the phase-specific implementation plan and API contract before implementation begins.

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

**Outcome:** A payout is not marked paid until the provider confirms completion; queue redelivery and ambiguous network failures cannot silently cause a second transfer or release the same commissions for a duplicate request.

**Likely files:**
- Modify: `backend/app/db/models.py`, `backend/app/services/payout.py`
- Modify: `backend/app/api/v1/admin/payouts.py`, `backend/app/api/v1/public/webhooks.py`
- Modify: `backend/app/queue/client.py`, `backend/app/queue/handlers.py`, `backend/app/queue/worker.py`
- Modify: `backend/app/integrations/paypal.py`, `backend/app/core/config.py`
- Create: next Alembic revision under `backend/alembic/versions/`
- Test: `backend/tests/test_payout.py`; add provider/webhook tests in focused payout test modules as appropriate

**Implementation sequence:**

- [ ] Write failing tests for duplicate approval, repeated worker delivery, provider rejection, timeout after provider acceptance, webhook success, webhook failure, and payout rejection. Assert each commission can belong to at most one active payout and is not released when the provider result is unknown.
- [ ] Define permitted payout status transitions and validate them server-side. The worker must accept only a payout in an eligible state and must be safe when the same queue message is delivered more than once.
- [ ] Replace the constant PayPal `sender_batch_id` with a deterministic payout-specific idempotency key. Persist provider batch/item identifiers and provider status before finalizing the ledger.
- [ ] Verify PayPal webhook authenticity and correlate webhook events to the stored payout. Only provider-confirmed completion may mark a payout and its associated commissions paid.
- [ ] Keep ambiguous provider outcomes in a reconcilable state; query/reconcile provider status before retrying or making commissions available again.
- [ ] Make payout creation and commission reservation atomic. Use a row-lock or conditional state update to prevent two concurrent requests from reserving the same available commissions.
- [ ] Make queue publication durable relative to the payout approval transaction. Prefer a persisted outbox or document and test an equivalent mechanism that prevents approved payouts from being stranded if queue publication fails.
- [ ] Implement merchant-specific funding/credentials only after the funding-model decision in Section 3. If the decision is platform-funded, add explicit merchant liability and settlement accounting instead of implying merchant-owned PayPal payouts.

**Acceptance criteria:**

- A provider timeout cannot cause automatic commission release until the provider outcome is known.
- Duplicate messages and repeated approval requests do not create duplicate transfers.
- Every payout has an auditable transition history and provider correlation data.
- Failed/rejected payments return commissions to an eligible balance exactly once; completed payouts do not.
- The stored payout amount, currency, withholding, provider-reported result, and affiliate-visible state reconcile.

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
| Payout reconciliation | Every payout reaches a provider-confirmed terminal state or a visible, actionable reconciliation state | P0 payout tests and sandbox reconciliation pass |
| Ledger accuracy | Dashboard, affiliate balance, payout request, and provider result reconcile by currency | P0 ledger examples reconcile exactly under documented rounding |
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
