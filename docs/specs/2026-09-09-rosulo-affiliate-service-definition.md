# Rosulo Affiliate Service — Service Definition

**Version:** 0.11
**Date:** 2026-10-01
**Status:** Draft — aligned to commission-backed manual payouts
**Audience:** Engineering, Product, allbum.me integration team, future SaaS customers

---

## 1. Purpose

The Rosulo Affiliate Service is a multi-tenant affiliate tracking and commission platform. It is built to power the allbum.me affiliate program and, later, to be sold as a standalone SaaS product to third-party merchants.

The service tracks campaign-driven click, lead, and merchant-confirmed sale events; computes affiliate commissions according to contract terms; makes commissions payable on the merchant-provided `good_date`; and records merchant-approved, manually completed PayPal payouts. Rosulo does not initiate or hold payout funds.

---

## 2. In Scope (v1)

- Multi-tenant merchant (tenant) onboarding and data isolation.
- Tenant user accounts (email/password login) that can manage one tenant account.
- API key management per tenant for server-to-server event ingestion.
- Affiliate accounts are created only by accepting a tenant invitation; a global account can be linked to multiple tenants over time.
- Per-tenant affiliate record with its own contract, campaigns, commissions, and payouts.
- Affiliate approval workflow, including a hard gate before the first payout.
- One contract per affiliate, managed by the tenant, defining commission terms by payment sequence.
- Campaign and tracking-code creation and management by the affiliate.
- Ingestion of `click`, `lead`, and `sale` events. A sale event is sent after the merchant confirms customer payment and must include `good_date`.
- Commission ledger states: `pending`, `available`, `reserved`, `paid`, and `reversed`, with currency-scoped amounts and tax retention.
- Daily promotion of pending commissions when the merchant-defined `good_date` is due.
- Affiliate payout requests for all available commissions or selected whole commission records in one currency; the server derives all amounts.
- Merchant review of the itemized commission batch, approval/rejection, and manual PayPal payment recording.
- Payout history, paid payout totals, and affiliate email notification with a payout detail link.
- Affiliate, tenant, and admin dashboards for campaign, commission, and payout management.
- Public API for event ingestion and data retrieval.
- Responsive web application for desktop and mobile.

## 3. Out of Scope (v1)

- Native iOS/Android mobile applications.
- PayPal API payout dispatch, PayPal payout webhooks, or any automated payout rail.
- Payment rails other than manual PayPal for affiliate settlement.
- Incoming customer payment-record ingestion/storage as a prerequisite for sale-event commission creation.
- Refund/chargeback event handling and commission reversal implementation; future refund events retain the external sale `payment_record_id` for correlation.
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
| **PayPal** | External payment service used by the merchant outside Rosulo to transfer funds to the affiliate; Rosulo records the merchant-confirmed payment. |

---

## 5. Domain Model

### 5.1 Bounded Contexts

1. **Tenant Management** — onboarding, billing, settings, isolation.
2. **Affiliate Management** — profiles, KYC documents, tax info, approval status, payout instructions.
3. **Campaign & Tracking** — campaign codes, links, event ingestion, attribution.
4. **Contracts & Terms** — per-affiliate commission rules bound to payment sequences.
5. **Sales & Commissions** — merchant-confirmed sale event processing, tax retention, due-date maturity, and commission ledger.
6. **Payouts** — whole-commission request selection, merchant review, manual PayPal payment recording, reconciliation, and reporting.
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
├── Commission[]
└── Payout[]

TenantUser
├── tenant_id
├── email
├── password_hash
├── name
└── role: admin | manager

AffiliateInvite (created by a tenant for an affiliate email)
├── tenant_id
├── email
├── token
├── contract_terms
├── status: pending | accepted | expired
└── expires_at

An invite has two outcomes depending on whether the email already has an `AffiliateAccount`:
- **Registration invite:** creates a new `AffiliateAccount` and a per-tenant `Affiliate` on acceptance.
- **Association invite:** creates only a per-tenant `Affiliate` linked to the existing `AffiliateAccount` on acceptance.

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
├── type: click | lead | sale | (future) refund
├── tenant_id
├── campaign_id
├── affiliate_id
├── customer_id
├── amount
├── currency
├── payment_sequence
├── good_date (required for sale; merchant-defined due date)
├── payment_record_id (required external merchant identifier on sale)
├── referer
├── page_url
└── occurred_at

Commission
├── event_id
├── affiliate_id
├── campaign_id
├── gross_amount
├── withholding_amount
├── net_amount
├── currency
├── status: pending | available | reserved | paid | reversed
└── available_at (good_date at 00:00 UTC)

Payout
├── affiliate_id
├── commission_ids (whole commission rows; one currency)
├── requested_amount (derived gross total)
├── approved_amount (derived gross total approved for payment)
├── withholding_total
├── net_paid
├── currency
├── status: pending_approval | approved | rejected | paid
├── requested_at
├── approved_at
└── paid_at

PayoutPayment
├── payout_id (unique)
├── amount
├── currency
├── payment_method: paypal
├── transfer_reference
├── paid_at (merchant-entered actual payment datetime)
└── recorded_by_tenant_user_id
```

---

## 6. Event Tracking

The service ingests three primary event types from the tenant or from the allbum.me product:

| Event Type | Trigger | Key Payload |
|------------|---------|-------------|
| `click` | A customer clicks or opens a campaign link, or the campaign code is computed on a page. | `campaign_id`, `customer_id`, `referer` (source page), `page_url` (page where the click was computed), `user_agent`, `ip_address`, `occurred_at` |
| `lead` | A customer registers or signs up and is attributed to a campaign. | `campaign_id`, `customer_id`, `customer_email`, `occurred_at` |
| `sale` | The merchant sends an event after its system confirms the customer payment. | `campaign_id`, `customer_id`, `amount`, `currency`, required external `payment_record_id`, `payment_sequence`, required `good_date`, `occurred_at` |

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

## 8. Sale Confirmation, Good Date, and Commission Availability

### 8.1 Sale Event as Payment Confirmation

The merchant sends a `sale` event only after its own system confirms the customer payment. Every sale event must include a nonblank merchant external `payment_record_id`; Rosulo stores that identifier only on the event for traceability and future refund-to-sale correlation. Rosulo does not require or persist a separate incoming customer `PaymentRecord` to create or mature a commission.

A future `refund` event must refer to the original sale's external `payment_record_id`. Refund ingestion and reversal behavior are not part of this version.

### 8.2 Merchant-Defined Good Date

`good_date` is required on every sale event. It is the due date selected by the merchant. Rosulo uses it directly and does not add another 14-day hold. Because the event field is date-only, Rosulo interprets `good_date` as 00:00 UTC and derives the commission's `available_at` timestamp from it.

A daily UTC process promotes commissions from `pending` to `available` when `available_at <= now_utc`. The process is idempotent, independent of affiliate page visits, and catches up after missed runs. A missing `good_date` is a sale validation error; the service must not substitute the current date.

### 8.3 Balance States

| State | Definition |
|-------|------------|
| **Earned** | Commission calculated from a merchant-confirmed sale event; reported separately from payout payments. |
| **Pending** | Commission with an `available_at` later than the current time. |
| **Available** | Commission whose due instant has passed and which is not reserved by an active payout. |
| **Reserved** | Commission associated with a payout in `pending_approval` or `approved` state. |
| **Paid** | Commission included in a payout with a completed merchant-confirmed payment. |
| **Reversed** | Existing ledger state for a reversal; refund event ingestion/reversal implementation remains deferred. |

A payout rejection returns its reserved commissions to `available` while retaining historical payout associations. An approved payout keeps commissions reserved until the merchant records the completed PayPal payment.

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

The merchant manually transfers the `net_paid` amount via PayPal outside Rosulo; the `withholding_total` is tracked separately. Rosulo records the merchant-entered payment datetime and PayPal reference but does not call PayPal.

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

### 11.1 Affiliate Request

1. The affiliate views available commissions and chooses either all available commission rows of one currency or a selected group of whole commission IDs.
2. The client does not submit an amount. Rosulo validates ownership, currency, status, and payout eligibility, then derives gross, withholding, and net totals from the selected ledger rows.
3. In one transaction, the service creates a `Payout` in `pending_approval`, links every selected commission, changes them from `available` to `reserved`, and records the initial transition.
4. A commission may belong to at most one active payout. A rejected payout retains its commission links for audit and returns its commissions to `available` for a later request.

### 11.2 Merchant Review and Approval

- A tenant user reviews the full commission batch, including every commission record, gross/withholding/net totals, count, and source sale date range.
- The tenant user may approve or reject a `pending_approval` payout. Only the tenant's authorized user may take the action.
- Approval changes the payout to `approved`; commissions remain `reserved`. No PayPal API call or payout queue message is triggered.
- Rejection changes the payout to `rejected` and releases all linked commissions to `available` atomically. Historical associations and status transitions remain visible.

### 11.3 Manual PayPal Payment

- The merchant performs the transfer outside Rosulo. The payment modal shows the affiliate name, contact email, PayPal recipient identifier, payout amount/currency, and commission count.
- After the transfer, the merchant records the actual payment datetime and PayPal transaction ID/reference. Amount and currency are derived from the approved payout.
- Successful confirmation creates one `PayoutPayment` and atomically marks the payout and its reserved commissions `paid`. A duplicate identical confirmation is idempotent; conflicting details are rejected.
- `PayoutPayment` stores the payout, amount, currency, `paypal` method, transfer reference, actual `paid_at`, and confirming tenant user. Legacy payout-linked payment records are migrated without loss.
- The affiliate receives a transactional email with a link to the authenticated payout detail after the payment commits. Email failure does not undo payment and must be retryable/observable.

### 11.4 Payout History and Reporting

- Affiliates can inspect payout status, linked commissions, and payment details from payout history/detail.
- Merchants can inspect an affiliate's payout history and paid payout totals for rolling 12 months and calendar YTD, grouped by payout payment date and currency.
- Reports never combine currencies. Paid payout totals are separate from earned commission totals.

---

## 12. Dashboards

### 12.1 Affiliate Dashboard

- **Registry volume** — total registrations grouped by day and by hour.
- **Payments by sequence** — 1st, 2nd, 3rd, etc. payments with associated commissions.
- **Campaign filter** — view data for one campaign or all campaigns.
- **Balance summary** — earned, pending, available, paid, tax retained, and any debt from reversals.
- **Payout history** — requested, approved, rejected, and paid payouts; payout detail shows included commissions and recorded PayPal payment details.
- **Document status** — KYC forms and approval state.

### 12.2 Tenant Dashboard

- Campaign performance (clicks, leads, conversion rate).
- Affiliate list and approval status.
- Commission liability by period, including tax retention totals.
- Payout request queue with complete commission detail and approval/rejection workflow.
- Per-affiliate payout history and paid payout totals for rolling 12 months and calendar YTD, separated by currency.
- Event stream and audit log.

### 12.3 Admin Dashboard

- Tenant provisioning, status, and billing.
- Global settings, supported currencies, and payout workflow support tools.
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
- `POST /v1/auth/affiliate/accept-invite` — affiliate accepts an invite token.
  - If the email has no `AffiliateAccount`, the payload must include `email`, `password`, `name`, `country`, and `token`; the account is created and linked to the tenant.
  - If the email already has an `AffiliateAccount`, the payload must include `email` and `token`; a new per-tenant `Affiliate` is created and linked.

### Affiliate — Tenant Selection

- `GET /v1/affiliate/merchants` — list tenants the affiliate account is linked to.
- `POST /v1/affiliate/merchants/:tenant_id/select` — set the active tenant for the session (also sent as `X-Tenant-Id`).

### Admin — Tenant & API Keys

- `GET /v1/admin/tenant` — get tenant profile.
- `POST /v1/admin/api-keys` — create a new API key for integration.
- `GET /v1/admin/api-keys` — list API keys (metadata only).
- `DELETE /v1/admin/api-keys/:id` — revoke an API key.

### Admin — Affiliates

- `POST /v1/admin/affiliates` — create an `AffiliateInvite` for an email with contract terms.
  - If no `AffiliateAccount` exists for the email: the invite is a registration invite; on acceptance the account is created and linked to the tenant.
  - If an `AffiliateAccount` already exists for the email: the invite is an association invite; on acceptance a new `Affiliate` record links the existing account to the tenant.
  - The platform sends an email with a tokenized invite link; the actual email dispatch may be a logging stub in v1.
- `GET /v1/admin/affiliates` — list accepted affiliates and pending invites for a tenant.
- `GET /v1/admin/affiliates/:id` — get affiliate profile, payout history, and paid payout totals for rolling 12 months and calendar YTD by currency.
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
- `GET /v1/admin/payouts/:id` — return payout totals, transition history, affiliate payment identity, and every linked commission/source sale.
- `POST /v1/admin/payouts/:id/approve` — approve a pending payout; this does not dispatch a PayPal transfer.
- `POST /v1/admin/payouts/:id/reject` — reject a pending payout and release its commissions (tenant-authorized user only).
- `POST /v1/admin/payouts/:id/confirm-payment` — record merchant-completed PayPal payment using `paid_at` and `transfer_reference`; amount/currency are derived from the payout.

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
- `POST /v1/affiliate/payout-requests` — request a payout using `currency` and optional whole `commission_ids`; omission selects all available rows in that currency, and the server derives the amount.
- `GET /v1/affiliate/payouts` — list own payouts from the selected tenant.
- `GET /v1/affiliate/payouts/:id` — view own payout commissions, status, and payment details.

### Webhooks and Events

- `POST /v1/events` — tenant sends a sale event after customer payment confirmation; each sale requires merchant-defined `good_date` and external `payment_record_id` for future refund correlation.
- PayPal payout webhooks and incoming customer payment-record webhooks are not part of the manual payout product.

### Dashboard Aggregations

- `GET /v1/affiliate/dashboard` — affiliate dashboard data.
- `GET /v1/admin/dashboard` — tenant / admin dashboard data.

---

## 14. Multi-Tenancy and SaaS Model

- Each tenant has its own isolated dataset, identified by `tenant_id` on every entity.
- SaaS pricing is out of scope for this service definition and will be defined separately.
- Tenant-level configuration includes: supported currencies, required KYC documents, default withholding rates, backup withholding rules, country/status-specific withholding overrides, and commission rounding rules. Affiliate PayPal recipient details are provided to the merchant for manual transfer; Rosulo does not store merchant PayPal API credentials.
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
- **Scheduled work:** EventBridge Scheduler launches a one-shot ECS/Fargate maintenance task daily at 00:15 UTC to mature due commissions and recover pending payout notices. The task is independent of App Runner API replicas. Do not use SQS/PayPal payout dispatch for manual settlement.
- **Frontend:** responsive web application (desktop and mobile).

### 16.2 Key Invariants

1. An affiliate account can be linked to many tenants; it has exactly one active per-tenant record per tenant.
2. An affiliate has exactly one active contract per tenant.
3. Affiliates create campaigns; commissions are calculated using the affiliate's contract regardless of which campaign generated the event.
4. Payouts aggregate commissions across campaigns for an affiliate within one tenant, but include only the whole commission rows selected by the affiliate.
5. An affiliate cannot request or receive a payout from a tenant if that tenant's per-tenant payout eligibility is not approved.
6. A payable sale event requires merchant-provided `good_date`; it is the due date and is interpreted as 00:00 UTC.
7. Only the daily maturity process transitions due commissions from `pending` to `available`; no incoming `PaymentRecord` is required.
8. A commission may be in at most one active payout; rejection releases it but preserves historical association.
9. A payout can become `paid` only after a merchant confirms external PayPal payment and one `PayoutPayment` is committed with it.
10. Events and payout/payment mutations are idempotent and tenant-scoped; currency totals never mix currencies.

---

## 17. Open Questions and Decisions

| # | Question | Impact | Default / Recommendation |
|---|----------|--------|--------------------------|
| 1 | What commission base and fee treatment apply to each contract? | Commission and payout net amounts. | Preserve existing contract/tax calculations; no new fee allocation is introduced by this payout change. |
| 2 | How is payment sequence number determined for repeated customer payments? | Commission attribution. | Resolve in the event/attribution contract; future refund events use the original sale's external `payment_record_id`. |
| 3 | What are the exact default withholding rules by affiliate status, and how are treaties / backup withholding handled? | Tax computation and payout net amount. | Existing tax scope remains subject to qualified tax/accounting review; this payout design does not validate tax law. |
| 4 | Which scheduler runtime, timeout, and alert channel will run daily commission maturity? | Due commissions may remain pending if scheduling fails. | EventBridge Scheduler runs the ECS/Fargate maintenance task at 00:15 UTC; the job has a 10-minute deadline, CloudWatch task logs, and idempotent catch-up. Verify in non-production before launch. |
| 5 | What retention/archive policy applies to any historical incoming `PaymentRecord` rows before the old table is removed? | Data preservation and migration safety. | Preserve/export existing rows or fail closed; never silently discard them. |
| 6 | Which durable retry mechanism will deliver paid-payout email notices? | Affiliate may not receive payment confirmation. | Persist `PayoutNotification` with payment, attempt email after commit, expose pending/sending/sent/failed status and merchant retry, and recover pending/expired leases in daily maintenance; use 5-second connect/15-second read timeouts. |
| 7 | Does v1 require a minimum payout threshold? | Affiliate request eligibility. | No minimum threshold is introduced by this design; requests contain all or selected available whole commissions, not a user-entered amount. |

---

## 18. Acceptance Criteria (v1)

1. A tenant user can log in with email/password and manage their tenant account, including API keys.
2. A tenant can create an affiliate invite for an email with contract terms; accepting the invite creates a new affiliate account when needed, or links an existing account, and creates the per-tenant affiliate record.
3. An affiliate can create one or more campaigns.
4. The service can ingest `click`, `lead`, and `sale` events and attribute them to a campaign.
5. Every `click` event records the `referer` and `page_url`.
6. The service calculates commissions from the affiliate's contract, not per campaign.
7. The service applies the correct withholding rate for each affiliate (US person 0% or 24% backup withholding; non-US person 30% or treaty rate) and records gross, withholding, and net amounts.
8. The service calculates commissions only for payment sequences covered by a term.
9. A sale event is sent after merchant payment confirmation and requires `good_date` plus the external `payment_record_id`; commissions become available on a daily UTC run at or after the merchant-defined due instant.
10. An affiliate cannot request a payout until per-tenant payout eligibility is approved.
11. An affiliate requests all or selected available whole commissions; the tenant reviews the itemized batch and manually pays by PayPal, then records actual payment time and reference.
12. The affiliate dashboard shows lead volume by day/hour and sales grouped by sequence, with optional campaign filter.
13. The tenant dashboard shows campaign performance, affiliate status, commission liability, and payout request queue.
14. An affiliate can log in, list linked merchants, select a merchant, and interact with each merchant's data using `X-Tenant-Id`.

---

## 19. Glossary

| Term | Definition |
|------|------------|
| **Clicks** | Customer interactions with a campaign, e.g. clicks or impressions. |
| **Leads** | Customer registrations or sign-ups attributed to a campaign. |
| **Sales** | Customer purchases attributed to a campaign after the merchant confirms payment and sends a sale event. |
| **Good Date** | Merchant-provided due date for commission availability; interpreted as 00:00 UTC on that date. |
| **PayoutPayment** | Immutable record of a merchant-confirmed external PayPal transfer for one affiliate payout. |
| **Term** | A rule that maps a payment sequence to a commission percentage. |
| **Contract** | The set of terms that belong to one affiliate. |
| **Affiliate Account** | The global identity (login, profile, documents, tax info) created when an affiliate accepts a tenant invitation. It can be linked to multiple tenants over time. |
| **Affiliate Invite** | A token/link created by a tenant that lets an affiliate register an account and be linked to that tenant. |
| **Affiliate** | The per-tenant record that links an affiliate account to a merchant, with its own contract, campaigns, commissions, and payouts. |
| **Tenant** | A merchant account using the affiliate platform. |
| **Tenant User** | A person at the merchant who logs in to manage the tenant account. |

---

*This is a draft service definition. Review, challenge, and update before moving to implementation planning.*
