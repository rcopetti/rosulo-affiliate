# Tenant-Scoped Event Idempotency

**Date:** 2026-09-30

**Status:** Implemented; verification complete

## Goal

Make external event identifiers unique within a tenant rather than globally. A tenant retry must return that tenant's original event; another tenant using the same identifier must create and receive its own event without learning anything about the first tenant's event.

## Scope

Implement only P0 Workstream 0.1 from `2026-09-30-affiliate-service-next-phase-execution-plan.md`:

- Scope event idempotency lookup to the authenticated tenant.
- Enforce `(tenant_id, event_id)` uniqueness in the database.
- Preserve same-tenant sale retry behavior so a retry does not create another commission.
- Add API regression coverage for cross-tenant identifier reuse, same-tenant retries, and the migration.

Do not change payout, withholding, currency calculation, KYC, onboarding, attribution, or browser-SDK behavior in this workstream.

## Decisions and dependencies

- **Payout funding:** Merchant-funded for the next release. This decision does not change this workstream.
- **Currency:** Multi-currency for the next release. This workstream does not change currency handling or permit mixed-currency aggregation.
- **Tax/withholding:** Qualified tax/accounting advice is pending. Payout and withholding changes remain blocked until the supported jurisdictions and policy are confirmed.
- **Attribution:** Deferred for this P0 workstream. Resolve lookback window, source precedence, and repeat-conversion behavior before productizing a browser tracking SDK.

## API contract

`POST /api/v1/events` keeps its current request and response schema and API-key tenant authentication.

- If `(authenticated_tenant.id, request.event_id)` already exists, return that tenant's stored event. Do not create another event or commission for the retry.
- If the same `event_id` exists only under another tenant, ingest a new event for the authenticated tenant and return that new event. The response must not contain the other tenant's event ID, tenant ID, or event details.
- The database, not only the application lookup, enforces uniqueness of `(tenant_id, event_id)`.

## Data model and service behavior

Change `Event` from a globally unique `event_id` column to a named composite unique constraint on `(tenant_id, event_id)`. Remove the existing standalone unique index on `event_id`; the composite constraint supports the tenant-scoped lookup.

Update `ingest_event` to query using both `tenant.id` and `data.event_id`. Retain first-write-wins behavior for same-tenant retries. Keep the existing API-layer commission idempotency behavior and prove it with a repeated sale test.

## Migration and compatibility

The repository's current Alembic head is `f7a8b9c0d123`. Add the next revision from that head. The upgrade removes the global unique index and adds the composite unique constraint without rewriting event rows. Existing data could not contain cross-tenant duplicate `event_id` values under the current global constraint, but verify this assumption against a representative copy before rollout.

A downgrade restores global uniqueness. Since the new schema can accumulate the same `event_id` in multiple tenants, the downgrade must check for such collisions and fail clearly rather than deleting or merging events. Exercise upgrade and downgrade against a disposable representative database copy.

The normal test fixture uses `Base.metadata.create_all()` rather than Alembic, so ORM/API tests alone do not verify migration correctness.

## Tests

- Ingest an event for tenant A, then submit the same `event_id` through tenant B's API key. Assert tenant B receives its own event and tenant A's event details are not returned.
- Retry an event with the same tenant and `event_id`. Assert the response identifies the original event and only one event row exists.
- Retry a sale for the same tenant and `event_id`. Assert only one commission is created.
- Exercise migration upgrade and guarded downgrade on a disposable database copy, including the downgrade collision case.
- Run focused event/tracking tests, then the complete backend suite, using an explicitly disposable test database. The current test fixture drops all tables in its configured test database at session startup; do not point it at a database containing data that must be retained.

## Out of scope

- Payout lifecycle, merchant-specific provider credentials, merchant settlement, and liability accounting.
- Tax advice, withholding rule changes, and payout currency behavior.
- Attribution windows, attribution precedence, repeat-conversion policy, and browser SDK implementation.
- General event/commission transaction redesign beyond the specified retry behavior.
