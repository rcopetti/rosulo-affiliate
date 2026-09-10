# Rosulo Affiliate Service — Service Definition

**Version:** 0.10  
**Date:** 2026-09-09  
**Status:** Draft — updated for tenant users and affiliate invitations  
**Audience:** Engineering, Product, allbum.me integration team, future SaaS customers

---

## 1. Purpose

The Rosulo Affiliate Service is a multi-tenant affiliate tracking and payout platform. It is built to power the allbum.me affiliate program and, later, to be sold as a standalone SaaS product to third-party merchants.

The service tracks campaign-driven click, lead, and sale events; computes affiliate commissions according to the affiliate's contract terms; and orchestrates approved payouts to affiliates.

---

## 2. In Scope (v1)

- Multi-tenant merchant (tenant) onboarding and data isolation.
- Tenant user accounts (email/password login) that can manage one tenant account.
- API key management per tenant for server-to-server integrations (events and webhooks).
- Affiliate accounts are created only by accepting a tenant invitation; a global account can be linked to multiple tenants over time.
- Per-tenant affiliate record with its own contract, campaigns, commissions, and payouts.
- Affiliate approval workflow, including a hard gate before the first payout.
- One contract per affiliate, managed by the tenant, defining commission terms by payment sequence.
- Campaign and tracking-code creation and management by the affiliate.
- Ingestion of three primary event types: `click`, `lead`, and `sale`.
- Contract terms that define commission percentages against specific payment sequences (1st, 2nd, 3rd, etc.).
- "Good date" handling for sale events and payment-record association.
- Commission ledger: earned, pending, available, and paid balances, including tax retention.
- Payout request, approval, and execution via PayPal.
- Affiliate dashboard with lead volume and sales grouping by sequence.
- Tenant and admin dashboards for campaign, affiliate, and payout management.
- Public API for event ingestion and data retrieval.
- Responsive web application for desktop and mobile.

## 3. Out of Scope (v1)

- Native iOS/Android mobile applications.
- Payment rails other than PayPal for payouts.
- Advanced attribution models beyond last-click / UTM campaign code.
- Built-in tax reporting or tax form generation.
- Automatic tax filing with government authorities.
- White-label customization beyond basic logo and colors.
- Public self-signup marketplace for affiliates.

---

## 4. Actors

| Actor | Description |
|-------|-------------|
| **Tenant / Merchant** | A business account running an affiliate program, e.g. allbum.me. Owns API keys, integrations, affiliates, and payout decisions. |
| **Tenant User** | A person at the merchant (admin) who logs in to manage the tenant account, invite affiliates, approve documents, manage contracts, and approve payouts. |
| **Affiliate / Partner** | A person or business invited by a tenant to promote its products. Creates a global account when accepting an invitation, and can later be invited by other tenants. Creates campaigns and requests payouts within the selected tenant. |
| **Platform Admin** | Rosulo operations staff who manage tenants, global settings, and compliance. |
| **End Customer** | The customer who clicks a campaign, registers, or pays. Not a direct user of the service. |
| **PayPal** | The payment rail used to move funds from the tenant to the affiliate. |

---

## 5. Domain Model

### 5.1 Bounded Contexts

1. **Tenant Management** — onboarding, billing, settings, isolation.
2. **Affiliate Management** — profiles, KYC documents, tax info, approval status, payout instructions.
3. **Campaign & Tracking** — campaign codes, links, event ingestion, attribution.
4. **Contracts & Terms** — per-affiliate commission rules bound to payment sequences.
5. **Sales & Commissions** — sale event processing, tax retention, and commission ledger.
6. **Payouts** — request, approval, batch creation, payment rail execution, reconciliation.
7. **Reporting & Dashboard** — aggregations for affiliates and tenants.

### 5.2 Core Entities

```
Tenant
├── name
├── api_key_hash
├── TenantUser[]
│   ├── email
│   ├── password_hash
│   ├── name
│   └── role: admin | manager
├── AffiliateInvite[]
│   ├── email
│   ├── token
│   ├── contract_terms
│   ├── status: pending | accepted | expired
│   └── expires_at
├── Affiliate[]
├── Event[]
├── PaymentRecord[]
└── Payout[]

TenantUser
├── tenant_id
├── email
├── password_hash
├── name
└── role: admin | manager

AffiliateInvite (created by a tenant)
├── tenant_id
├── email
├── token
├── contract_terms
├── status: pending | accepted | expired
└── expires_at

AffiliateAccount (created when an affiliate accepts an invitation)
├── email
├── password_hash
├── name
├── country
├── state
├── tax_id
├── tax_status
├── tax_form_type
├── documents[]
├── paypal_email
├── backup_withholding_required
└── Affiliate[] (one per tenant the account was invited to)
    ├── affiliate_account_id
    ├── tenant_id
    ├── kyc_approved_for_payout
    ├── contract
    │   └── Term[]
    │       ├── payment_sequence
    │       ├── commission_percent
    │       ├── effective_from / effective_to
    │       └── minimum_threshold
    ├── Campaign[]
    │   ├── tracking_code
    │   ├── landing_url
    │   └── affiliate_id
    ├── Commission[]
    └── Payout[]

Event
├── type: click | lead | sale
├── tenant_id
├── campaign_id
├── affiliate_id
├── customer_id
├── amount
├── currency
├── payment_sequence
├── good_date
├── payment_record_id
├── referer
├── page_url
└── occurred_at

PaymentRecord
├── tenant_payment_id
├── customer_id
├── amount
├── currency
├── paid_at
├── sequence_number
└── status: paid | refunded | charged_back

Commission
├── event_id
├── affiliate_id
├── campaign_id
├── gross_amount
├── withholding_amount
├── net_amount
├── currency
├── status: pending | available | paid | reversed
└── available_on

Payout
├── affiliate_id
├── campaign_filter (optional for reporting only; payout is cross-campaign)
├── requested_amount
├── approved_amount (gross commissions approved for payment)
├── withholding_total
├── paypal_fees
├── net_paid
├── currency
├── commissions[]
├── paypal_batch_id
├── status: requested | pending_approval | approved | processing | paid | failed | rejected
├── requested_at
├── approved_at
└── paid_at
```

---

## 6. Event Tracking

The service ingests three primary event types from the tenant or from the allbum.me product:

| Event Type | Trigger | Key Payload |
|------------|---------|-------------|
| `click` | A customer clicks or opens a campaign link, or the campaign code is computed on a page. | `campaign_id`, `customer_id`, `referer` (source page), `page_url` (page where the click was computed), `user_agent`, `ip_address`, `occurred_at` |
| `lead` | A customer registers or signs up and is attributed to a campaign. | `campaign_id`, `customer_id`, `customer_email`, `occurred_at` |
| `sale` | A customer pays the tenant. | `campaign_id`, `customer_id`, `amount`, `currency`, `payment_record_id`, `payment_sequence`, `good_date`, `occurred_at` |

### 6.1 Click Referer

Every `click` event must record:

- `referer` — the source page that sent the customer to the tracked page, if available.
- `page_url` — the page on which the click event was computed or recorded.

If the click is triggered by a direct link click, `referer` is the previous page and `page_url` is the landing page. If the click is computed on the tenant site after the campaign is resolved, both may be the tenant page.

### 6.2 Ingestion Channels

1. **REST API** — `POST /v1/events` for server-to-server tracking.
2. **JavaScript Pixel / Tag** — lightweight client-side event for `click` and `lead`.
3. **Webhooks** — the tenant (e.g. allbum.me) pushes sale events.

All events must be idempotent. Duplicates are recognized by a unique `event_id` or deterministic idempotency key and are ignored after the first successful write.

---

## 7. Contracts and Commission Rules

### 7.1 One Contract Per Affiliate

Each affiliate has exactly one active contract per tenant. The tenant creates the affiliate and defines the contract and its terms. Terms cannot be defined per campaign.

The affiliate may create multiple campaigns for traceability, internal organization, or different landing pages, but all commissions for that affiliate are calculated from the same contract.

### 7.2 Term Model

A contract is a collection of terms. Each term defines:

- **Payment sequence** — which customer payment the term applies to (e.g. `1` for first payment only, `2` for second, `*` for all, or a list like `1,3,5`).
- **Commission percentage** — the share owed to the affiliate.
- **Effective window** — start and end dates.
- **Minimum threshold** — optional minimum amount for the term to apply.

### 7.3 Sequence Exclusion

If a sale event has a sequence number that is not covered by any active term, the event is recorded in the event stream but does **not** generate a commission. This prevents confusion for affiliates and support staff.

### 7.4 Cross-Campaign Payouts

Affiliates can filter their dashboard by campaign, but payouts are always calculated across all campaigns for the affiliate. A payout request is per affiliate, not per campaign.

### 7.5 Refunds and Chargebacks

A refund or chargeback creates a reversal event. The system generates a negative commission of the same gross amount and payment sequence, reducing the affiliate's available balance. If the commission was already paid, the reversal is recorded as a debt against future earnings.

---

## 8. Payment Records and "Good Date"

### 8.1 PaymentRecord

A `PaymentRecord` is the authoritative proof of a customer payment in the tenant's system (e.g. allbum.me charge record or PSP record).

- `payment_record_id` — unique identifier from the merchant.
- `amount` and `currency`.
- `paid_at` — the moment the money changed hands.
- `sequence_number` — the 1st, 2nd, 3rd, etc. payment for that customer.
- `status` — `paid`, `refunded`, `charged_back`.

### 8.2 Good Date

The `good_date` on a sale event represents when the commission becomes available for payout. This is not necessarily the same as `paid_at`. For example, on allbum.me the `good_date` may be the event date on which the sale settles.

### 8.3 Balance States

| State | Definition |
|-------|------------|
| **Earned** | Commission calculated from a tracked sale event. |
| **Pending** | Commission with a `good_date` in the future. |
| **Available** | Commission with a `good_date` on or before today and a matching `PaymentRecord`. |
| **Paid** | Commission included in a completed Payout. |
| **Coming Revenue** | Sale event with a `good_date` but no `payment_record_id` yet. |

A sale with a `good_date` but no `payment_record_id` is treated as **coming revenue** and is not included in the affiliate's available balance until the matching `PaymentRecord` arrives.

---

## 9. Tax Withholding and Reporting

> **Disclaimer:** This section summarizes publicly available IRS guidance for product definition purposes only. It is not tax or legal advice. Final rates, forms, and filing obligations must be confirmed by a qualified tax professional before implementation.

### 9.1 Affiliate Tax Classification

The affiliate profile stores:

- `country` — country of residence / tax jurisdiction.
- `state` — US state or province, when applicable.
- `tax_id` — TIN, SSN, EIN, ITIN, or foreign equivalent.
- `tax_status` — `us_person` or `non_us_person`.
- `tax_form_type` — `W-9` for US persons; `W-8BEN` for non-US individuals; `W-8BEN-E` for non-US entities.
- `withholding_certificate` — uploaded and approved tax form.
- `backup_withholding_required` — flag for US persons subject to backup withholding.

### 9.2 US-Person Affiliates

For US persons (US citizens, residents, and US entities):

- Collect a completed Form W-9 before the first payout.
- Report annual nonemployee compensation on Form 1099-NEC if total payments are $600 or more in a calendar year ($2,000 for payments after December 31, 2025, under current law).
- No federal income tax is withheld by default.
- Backup withholding at **24%** applies if:
  - No TIN is provided on Form W-9,
  - The IRS notifies the payer that the TIN is incorrect,
  - The IRS notifies the payer that the affiliate underreported interest or dividend income, or
  - The affiliate fails to certify that they are not subject to backup withholding.
- The service records `gross_amount`, `withholding_amount`, and `net_amount` when backup withholding applies.

### 9.3 Non-US-Person Affiliates

For non-US persons (nonresident aliens and foreign entities):

- Collect a completed Form W-8BEN or W-8BEN-E before the first payout.
- US-source FDAP income (including many types of commission or referral fees) is subject to **30% NRA withholding** under IRC sections 1441–1443, unless:
  - A tax treaty reduces or eliminates the rate,
  - The income is effectively connected with a US trade or business (ECI), or
  - Another Internal Revenue Code exemption applies.
- The service reports gross income and withholding on Form 1042-S and supports the related Form 1042 filing workflow (the actual filing is out of scope for v1).
- The affiliate can claim treaty benefits by submitting a W-8BEN with a treaty claim; the tenant admin or platform admin reviews and overrides the default 30% rate.

### 9.4 Commission Withholding Calculation

When a commission is calculated:

- `gross_amount` = commission before withholding.
- `withholding_amount` = `gross_amount` × applicable withholding rate.
- `net_amount` = `gross_amount` − `withholding_amount`.
- The `withholding_amount` is accumulated on the payout record and on the tax reporting summary.

Default withholding rates are tenant-configurable:

- US person with valid W-9 and no backup-withholding trigger: `0%`.
- US person subject to backup withholding: `24%`.
- Non-US person with no treaty: `30%`.
- Non-US person with valid treaty claim: configurable reduced rate or `0%` as documented on the W-8BEN.

A tenant may define country- or status-specific withholding overrides that take precedence over the system defaults. This is a short-term safety valve; a future release should replace overrides with a rules engine validated by a tax advisor that derives the correct rate from residency, income type, treaty status, and approved withholding certificates.

### 9.5 Payout Withholding

A payout record stores:

- `gross_commissions` — sum of gross commission amounts included.
- `withholding_total` — total tax withheld.
- `paypal_fees` — PayPal transaction fees, if borne by the affiliate.
- `net_paid` — amount sent to the affiliate (`gross_commissions` − `withholding_total` − `paypal_fees`).

Only the `net_paid` amount is transferred via PayPal. The `withholding_total` is tracked for later remittance and reporting.

Note: The service computes and tracks withholding values. Actual remittance to tax authorities and generation of official tax documents is outside the scope of v1.

---

## 10. KYC and Payout Eligibility

### 10.1 Required Business Forms

Before an affiliate can request or receive a payout from a tenant, the affiliate account must upload and have approved the required business forms. The exact forms are configurable per tenant but default to:

- Business registration / proof of identity.
- Tax form (W-9 for US persons, W-8BEN for non-US persons, or local equivalent).
- PayPal payment instructions.

### 10.2 Approval Workflow

1. The affiliate account uploads documents once (stored on the global account).
2. The tenant admin reviews the documents and approves or rejects the per-tenant KYC/payout eligibility.
3. Payout requests for a tenant are blocked until that tenant's per-tenant affiliate record is KYC-approved.
4. Document expiry and re-verification are flagged but not part of v1 scope.

---

## 11. Payouts

### 11.1 Payout Request

1. The affiliate views their available balance (cross-campaign) and submits a payout request.
2. The service calculates the gross commission, applies the applicable withholding, and creates a `Payout` in status `requested`.
3. The payout remains in `pending_approval` until the tenant approves it.

### 11.2 Payout Approval

- A tenant admin reviews the requested payout. The platform (Rosulo) does not participate in payout approval decisions; this remains the tenant's business.
- On approval, the payout moves to `approved`, then `processing` while the PayPal batch is created.
- On rejection, the payout moves to `rejected` and the commission becomes available again.

### 11.3 PayPal Execution

- The service uses the PayPal Payouts API to send funds from the tenant's PayPal account to the affiliate's PayPal email.
- Only the `net_paid` amount is transferred; the `withholding_total` is tracked separately.
- Each payout item is logged with the PayPal batch id, item id, status, amount, currency, and fees.
- Payouts are idempotent; the same request cannot be approved and paid twice.

### 11.4 Reconciliation

- On PayPal success, commissions transition from `available` to `paid` and the payout status becomes `paid`.
- On failure, the payout status becomes `failed` and the commissions remain `available` for the next request.

---

## 12. Dashboards

### 12.1 Affiliate Dashboard

- **Registry volume** — total registrations grouped by day and by hour.
- **Payments by sequence** — 1st, 2nd, 3rd, etc. payments with associated commissions.
- **Campaign filter** — view data for one campaign or all campaigns.
- **Balance summary** — earned, pending, available, paid, tax retained, and any debt from reversals.
- **Payout history** — requested, approved, and paid payouts with PayPal transaction details.
- **Document status** — KYC forms and approval state.

### 12.2 Tenant Dashboard

- Campaign performance (clicks, leads, conversion rate).
- Affiliate list and approval status.
- Commission liability by period, including tax retention totals.
- Payout request queue and approval workflow.
- Payout batch history.
- Event stream and audit log.

### 12.3 Admin Dashboard

- Tenant provisioning, status, and billing.
- Global settings, supported currencies, and PayPal rail configuration.
- Support tools to inspect events, commissions, and payouts.

---

## 13. API Surface (v1 Draft)

All endpoints are prefixed with `/v1` and require role-scoped, tenant-scoped authentication.

- `/v1/auth/tenant/login` returns a tenant-scoped JWT for a `TenantUser`.
- `/v1/admin/*` endpoints are for authenticated tenant users. The `TenantUser` belongs to exactly one tenant; the JWT carries the tenant id.
- `/v1/affiliate/*` endpoints are for the authenticated affiliate account. The affiliate account id is taken from the JWT. All affiliate-scoped endpoints require a `X-Tenant-Id` header that selects the active merchant/tenant; the service resolves the per-tenant `affiliate_id` from the account + tenant. No `:id` path parameter is exposed for affiliate-scoped endpoints, preventing cross-affiliate and cross-tenant access.
- `POST /v1/events` and inbound webhooks use a tenant API key (server-to-server integration authentication).
- Webhooks are verified with a per-webhook shared secret or signature where applicable.

### Events

- `POST /v1/events` — ingest an event (tenant API key).
- `GET /v1/admin/events` — list and filter events for a tenant.

### Auth

- `POST /v1/auth/tenant/login` — tenant user login with email/password, returns a tenant-scoped JWT.
- `POST /v1/auth/affiliate/login` — affiliate login, returns JWT.
- `POST /v1/auth/affiliate/accept-invite` — affiliate creates or links a global account by accepting a tenant invitation.

### Affiliate — Tenant Selection

- `GET /v1/affiliate/merchants` — list tenants the affiliate account is linked to.
- `POST /v1/affiliate/merchants/:tenant_id/select` — set the active tenant for the session (also sent as `X-Tenant-Id`).

### Admin — Tenant & API Keys

- `GET /v1/admin/tenant` — get tenant profile.
- `POST /v1/admin/api-keys` — create a new API key for integration.
- `GET /v1/admin/api-keys` — list API keys (metadata only).
- `DELETE /v1/admin/api-keys/:id` — revoke an API key.

### Admin — Affiliates

- `POST /v1/admin/affiliates` — create an `AffiliateInvite` with contract terms; returns the invite token/link for the affiliate.
- `GET /v1/admin/affiliates` — list affiliates and pending invites for a tenant.
- `GET /v1/admin/affiliates/:id` — get affiliate profile.
- `PATCH /v1/admin/affiliates/:id` — update affiliate.
- `POST /v1/admin/affiliates/:id/documents/approve` — approve a business form.
- `POST /v1/admin/affiliates/:id/approve` — approve KYC for payouts.
- `POST /v1/admin/affiliates/:id/reject` — reject an affiliate or KYC.

### Admin — Affiliates

- `POST /v1/admin/affiliates` — create a global affiliate account and a per-tenant record with contract terms.
- `GET /v1/admin/affiliates` — list affiliates for a tenant.
- `GET /v1/admin/affiliates/:id` — get affiliate profile.
- `PATCH /v1/admin/affiliates/:id` — update affiliate.
- `POST /v1/admin/affiliates/:id/documents/approve` — approve a business form.
- `POST /v1/admin/affiliates/:id/approve` — approve KYC for payouts.
- `POST /v1/admin/affiliates/:id/reject` — reject an affiliate or KYC.

### Admin — Contracts

- `GET /v1/admin/affiliates/:id/contract`
- `PUT /v1/admin/affiliates/:id/contract` — update the affiliate's contract and terms.
- `POST /v1/admin/affiliates/:id/contract/terms` — add a term.
- `PATCH /v1/admin/affiliates/:id/contract/terms/:termId`

### Admin — Payouts

- `GET /v1/admin/payouts` — list payout requests for a tenant.
- `GET /v1/admin/payouts/:id`
- `POST /v1/admin/payouts/:id/approve` — approve and trigger PayPal (tenant admin only).
- `POST /v1/admin/payouts/:id/reject` — reject a payout request (tenant admin only).

### Affiliate — Self-Service

All endpoints below require the `X-Tenant-Id` header to select the active merchant.

- `GET /v1/affiliate/profile` — get global account profile.
- `PATCH /v1/affiliate/profile` — update global account profile.
- `POST /v1/affiliate/documents` — upload a business form to the global account.
- `GET /v1/affiliate/contract` — view own contract for the selected tenant.
- `POST /v1/affiliate/campaigns` — create a campaign under the selected tenant.
- `GET /v1/affiliate/campaigns` — list own campaigns under the selected tenant.
- `GET /v1/affiliate/campaigns/:id`
- `PATCH /v1/affiliate/campaigns/:id`

### Affiliate — Balances, Commissions and Payouts

All endpoints below require the `X-Tenant-Id` header to select the active merchant.

- `GET /v1/affiliate/balance`
- `GET /v1/affiliate/commissions`
- `POST /v1/affiliate/payout-requests` — request a payout from the selected tenant.
- `GET /v1/affiliate/payouts` — list own payouts from the selected tenant.

### Webhooks

- `POST /v1/webhooks/paypal` — PayPal IPN/Payouts webhook.
- `POST /v1/webhooks/tenant` — tenant push for payment records.

### Dashboard Aggregations

- `GET /v1/affiliate/dashboard` — affiliate dashboard data.
- `GET /v1/admin/dashboard` — tenant / admin dashboard data.

---

## 14. Multi-Tenancy and SaaS Model

- Each tenant has its own isolated dataset, identified by `tenant_id` on every entity.
- SaaS pricing is out of scope for this service definition and will be defined separately.
- Tenant-level configuration includes: supported currencies, required KYC documents, default withholding rates, backup withholding rules, country/status-specific withholding overrides, commission rounding rules, and PayPal credentials.
- 3rd-party tenants use the same API and web application; allbum.me is the first tenant.

---

## 15. Security and Compliance

- All data in transit over TLS; encryption at rest for databases and object storage.
- API authentication via API keys or OAuth 2.0, with tenant-scoped authorization.
- Rate limiting per API key and per tenant.
- KYC and tax documents stored in an encrypted object store with restricted access.
- GDPR / CCPA data deletion supported at tenant and affiliate level.
- Idempotency and audit logging on all financial mutations.
- Tax retention values are tracked for reporting only; official remittance and tax filing are out of scope for v1.

---

## 16. Technical Considerations

### 16.1 Architecture Style

- **Backend:** FastAPI (Python) modular monolith. Authentication is implemented in the service itself.
- **Deployment:** AWS App Runner.
- **API:** REST with JSON; OpenAPI specification generated from FastAPI.
- **Database:** relational (PostgreSQL) for transactional data, with optional OLAP/clickhouse for dashboard aggregations.
- **Queue:** Amazon SQS for background jobs such as payout execution and event processing.
- **Frontend:** responsive web application (desktop and mobile).

### 16.2 Key Invariants

1. An affiliate account can be linked to many tenants; it has exactly one active per-tenant record per tenant.
2. An affiliate has exactly one active contract per tenant.
3. Affiliates create campaigns; commissions are calculated using the affiliate's contract regardless of which campaign generated the event.
4. Payouts aggregate commissions across all campaigns for an affiliate within one tenant.
5. An affiliate cannot request or receive a payout from a tenant if that tenant's per-tenant KYC is not approved.
5. A commission is not marked `available` before its `good_date`.
6. A commission is not marked `available` without a matching `PaymentRecord`.
7. A payment sequence not covered by the affiliate's contract does not generate a commission.
8. Events are idempotent; duplicate ingestion does not create duplicate commissions.
9. Payouts are idempotent; a payout request cannot be approved and paid twice.

---

## 17. Open Questions and Decisions

| # | Question | Impact | Default / Recommendation |
|---|----------|--------|--------------------------|
| 1 | Should commission be calculated on gross or net amount (after refunds/fees)? | Revenue recognition and payout amounts. | Default to gross; fees handled by tenant separately. |
| 2 | How is payment sequence number determined when multiple payment records exist for one customer? | Commission attribution. | Sequence is ordinal by `paid_at` per customer. |
| 3 | What are the exact default withholding rules by affiliate status, and how are treaties / backup withholding handled? | Tax computation and payout net amount. | US persons: 0% unless backup withholding (24%). Non-US persons: 30% NRA unless treaty/ECI. Treaties require approved W-8BEN and admin override. |
| 4 | Are payouts automatic on a schedule or manually initiated? | Cash flow and operations. | v1: affiliate requests, tenant approves. |
| 5 | Who pays PayPal transaction fees — tenant or affiliate? | Payout net amount. | Tenant pays fees (affiliate receives the net commission amount). |
| 6 | What is the minimum payout threshold? | Support and transaction cost. | Configurable per tenant; default $50. |
| 7 | How are multi-currency sale events handled? | FX, rounding, payout currency. | v1: store event currency; payout in affiliate's configured currency at payout-time rate. |
| 8 | Who approves payout requests? | Operations and liability. | Tenant admin only. The platform does not participate in payout approval decisions. |

---

## 18. Acceptance Criteria (v1)

1. A tenant user can log in with email/password and manage their tenant account, including API keys.
2. A tenant can create an affiliate invite with contract terms; an affiliate can only create an account by accepting an invite.
3. An affiliate can create one or more campaigns.
4. The service can ingest `click`, `lead`, and `sale` events and attribute them to a campaign.
5. Every `click` event records the `referer` and `page_url`.
6. The service calculates commissions from the affiliate's contract, not per campaign.
7. The service applies the correct withholding rate for each affiliate (US person 0% or 24% backup withholding; non-US person 30% or treaty rate) and records gross, withholding, and net amounts.
8. The service calculates commissions only for payment sequences covered by a term.
9. A sale event with a `good_date` and no `payment_record_id` is not available for payout.
10. An affiliate cannot request a payout until KYC documents are approved.
11. An affiliate can request a payout; a tenant can approve it and trigger PayPal payment.
12. The affiliate dashboard shows lead volume by day/hour and sales grouped by sequence, with optional campaign filter.
13. The tenant dashboard shows campaign performance, affiliate status, commission liability, and payout request queue.
14. An affiliate can log in, list linked merchants, select a merchant, and interact with each merchant's data using `X-Tenant-Id`.

---

## 19. Glossary

| Term | Definition |
|------|------------|
| **Clicks** | Customer interactions with a campaign, e.g. clicks or impressions. |
| **Leads** | Customer registrations or sign-ups attributed to a campaign. |
| **Sales** | Completed customer purchases attributed to a campaign, confirmed by the payment record. |
| **Good Date** | The date on which a commission becomes eligible for payout. |
| **Coming Revenue** | A tracked sale that is expected but not yet confirmed by a payment record. |
| **Term** | A rule that maps a payment sequence to a commission percentage. |
| **Contract** | The set of terms that belong to one affiliate. |
| **Affiliate Account** | The global identity (login, profile, documents, tax info) created when an affiliate accepts a tenant invitation. It can be linked to multiple tenants over time. |
| **Affiliate Invite** | A token/link created by a tenant that lets an affiliate register an account and be linked to that tenant. |
| **Affiliate** | The per-tenant record that links an affiliate account to a merchant, with its own contract, campaigns, commissions, and payouts. |
| **Tenant** | A merchant account using the affiliate platform. |
| **Tenant User** | A person at the merchant who logs in to manage the tenant account. |

---

*This is a draft service definition. Review, challenge, and update before moving to implementation planning.*
