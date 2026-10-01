# Affiliate Per-Merchant Tax Document Review

**Date:** 2026-10-01

**Status:** Approved design; awaiting document review

## Goal

Make merchant tax-document review and affiliate payout eligibility tenant-specific, consistent between the API and UI, and auditable without sharing one merchant's review decision with another.

## Agreed implementation order

Complete Workstream 0.5, then implement Workstream 0.3 using per-merchant document copies, then return to Workstream 0.2. Workstream 0.3 does not change the tax calculation, withholding rules, payout funding model, or transfer lifecycle.

## Decisions

- **Document scope:** Every new tax-form upload belongs to the selected affiliate–merchant relationship. The affiliate account remains the identity owner, but a merchant can view and review only the copy uploaded for its own relationship.
- **Legacy account-wide uploads:** Preserve existing account-wide documents and their legacy approval values as unscoped history. Do not copy them to merchant relationships and do not use them for payout eligibility. Affiliates must upload a new copy for each merchant. Keep legacy history distinguishable from a merchant-reviewed document.
- **Supported purpose and types:** This workflow reviews the required tax form derived from the affiliate's tax status and entity type (W-9, W-8BEN, or W-8BEN-E). It is tax-document review, not general identity or business verification. Keep the server-accepted formats PDF, JPEG, PNG, and WebP and the current size limit.
- **Review state:** A new merchant-scoped submission starts pending. Its review state is pending, approved, or rejected. A decision records the tenant user, UTC decision time, and rejection reason; a rejection requires a non-empty reason. Review decisions are append-only so subsequent actions do not erase the audit trail. The latest decision is the current state; no decision means pending.
- **Eligibility:** For a given affiliate–merchant relationship, evaluate the newest submission matching the currently required tax-form type. No matching submission, pending review, or rejected review is ineligible. The latest decision for the newest submission must be approved for eligibility. A newer upload makes that relationship ineligible while the new submission is pending; it does not alter earlier submissions or decisions. Approval for one merchant never grants eligibility for another.
- **One backend policy:** A shared backend policy function computes eligibility and its reason. Payout creation enforces it regardless of the caller. The affiliate-facing API returns that same decision and the selected merchant's document states/reasons; the frontend does not independently infer eligibility from account-global documents.
- **Authorization and isolation:** Affiliate upload/list/view operations are scoped using the authenticated affiliate and selected `X-Tenant-Id`. Merchant review operations are scoped to a tenant user and an affiliate belonging to that same tenant. A document ID from another merchant relationship is not accessible or reviewable.
- **Re-upload history:** Each upload is a separate record. Earlier merchant-specific submissions and their review decisions remain available in that merchant's history. Legacy unscoped records remain preserved but cannot appear as that merchant's reviewed copy.

## Data model and API behavior

Add an optional affiliate-relationship reference to `AffiliateDocument`; it is null only for preserved legacy account-wide documents and is set for all new uploads. Keep the account reference for affiliate ownership. Add a review-decision model associated with a merchant-scoped document and a tenant user, containing the decision (`approved` or `rejected`), decision time, and optional rejection reason. Pending is derived when a merchant-scoped document has no decision. Query document and decision history only through the authenticated affiliate–tenant association.

Update `POST /api/v1/affiliate/documents` to require the authenticated affiliate relationship selected by `X-Tenant-Id`. Add a tenant-scoped affiliate document/status read that returns the relationship's submissions, review history/current status, required tax-form type, and payout eligibility/reason. Use this response in the affiliate uploader/profile and payout-request views. Keep account profile fields account-wide.

Replace affiliate-level approve/reject actions with a merchant action for a specific affiliate document. The review request contains `approved` or `rejected`; rejected decisions require a reason. Store the reviewer from the authenticated tenant user. Admin detail shows only that merchant's documents and review history, with explicit pending/approved/rejected states and rejection reasons.

The payout service calls the same eligibility function used by the status endpoint before reserving commissions. Ineligible requests receive a 403 response with the policy reason. The UI disables the request based on the API response and displays that reason.

## Migration and data safety

Create the next Alembic revision from the current head. Preserve old account-wide document rows and their legacy `approved` values, mark them as unscoped legacy records, and leave their relationship reference null. Preserve the old affiliate-level payout-approval value as legacy history, but stop using it for eligibility. Do not synthesize a merchant reviewer, decision time, rejection reason, or merchant-specific approval from either legacy boolean. New payout eligibility requires a new merchant-scoped upload and a decision by that merchant. A downgrade must fail clearly if merchant-scoped documents or review decisions exist, because the old schema cannot represent them without losing tenant scope or audit data.

The test fixture recreates its schema from ORM metadata rather than applying Alembic revisions. Migration upgrade/downgrade behavior therefore needs separate verification against a disposable database; do not treat ordinary API tests as migration validation.

## Tests

- Affiliate with no merchant-scoped tax document is ineligible, including when the account has only a legacy unscoped document.
- A pending or rejected newest submission blocks payout; rejection reason is returned to that affiliate in that merchant context.
- An approved newest submission permits the payout request; the backend independently rejects all ineligible requests.
- Two merchant relationships for one affiliate account have independent document lists, decisions, and eligibility; a document or review from one cannot be read or changed through the other.
- A rejection requires a reason and records the authenticated tenant user and decision time.
- A new upload becomes pending, preserves the previous submission and decision, and cannot inherit approval from the older document.
- Merchant detail and affiliate views render the same server-provided review state; the payout page uses backend eligibility/reason rather than evaluating document booleans.
- Upload type, required-form, maximum-size, and encryption behavior remain covered.
- Migration tests preserve legacy values, keep legacy rows unscoped/ineligible, and verify upgrade/downgrade on a disposable database.

## Out of scope

- Jurisdiction-aware tax advice, tax-rate or withholding changes, and general identity/business verification.
- Workstream 0.2 payout transfer state machine, provider webhooks, merchant settlement, and payout funding-model decisions.
- Workstream 0.4 onboarding and merchant-role policy beyond requiring an authenticated tenant user for document review.
- Global sharing or automatic copying of legacy uploads into merchant relationships.
