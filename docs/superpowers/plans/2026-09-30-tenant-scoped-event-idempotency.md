# Tenant-Scoped Event Idempotency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow the same external event ID in different tenants while preserving first-write-wins retries within a tenant.

**Architecture:** Replace global event-ID uniqueness with a database constraint on `(tenant_id, event_id)`, and apply that same pair in the event service lookup. Keep the existing public event request/response contract and commission handling; verify the cross-tenant boundary through the API.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, pytest, httpx.

---

## File Map

- Modify `backend/tests/test_events.py`: API regression coverage for duplicate IDs across tenants and same-tenant sale retries.
- Modify `backend/app/db/models.py`: declare the named composite uniqueness constraint and remove global uniqueness from `Event.event_id`.
- Modify `backend/app/services/event.py`: scope the idempotency lookup to the authenticated tenant and supplied event ID.
- Create `backend/alembic/versions/c2d3e4f5a6b7_tenant_scoped_event_idempotency.py`: migrate the existing global index to the composite constraint and guard downgrade when cross-tenant duplicates exist.
- Update the unchecked steps for Workstream 0.1 in `docs/superpowers/plans/2026-09-30-affiliate-service-next-phase-execution-plan.md` only after implementation and verification succeed. Leave all other workstreams unchanged.

## Test Database Safety Gate

`backend/tests/conftest.py` configures the test database and calls `Base.metadata.drop_all()` at session startup. Before running any pytest command below, obtain/verify an explicitly disposable PostgreSQL database and set `TEST_DATABASE_URL` to it. Do not allow the default configured database or any database with retained data to be used. Migration verification must use a separate disposable PostgreSQL database URL in `AFFILIATE_MIGRATION_DATABASE_URL`; never run the migration smoke steps against a production, shared, or data-retaining database.

### Task 1: Add API regression tests

**Files:**
- Modify: `backend/tests/test_events.py`

- [ ] **Step 1: Add the cross-tenant API test**

Add these imports to `backend/tests/test_events.py`:

```python
from sqlalchemy import func, select

from app.core.security import hash_api_key
from app.db.models import Affiliate, AffiliateAccount, Campaign, Commission, Event, Tenant
from app.db.session import async_session
```

Add this test. It creates valid campaigns for both tenants so each request passes event validation; the current global lookup will incorrectly return tenant A's event for tenant B and fail the tenant/id assertions.

```python
@pytest.mark.asyncio
async def test_event_idempotency_is_scoped_to_tenant(
    client: AsyncClient, tenant: Tenant
):
    tenant_b_api_key = "tenant-b-event-key"
    event_id = "cross-tenant-idempotency-event"

    async with async_session() as db:
        tenant_b = Tenant(
            name="second-merchant",
            api_key_hash=hash_api_key(tenant_b_api_key),
        )
        account_a = AffiliateAccount(
            email="event-tenant-a@example.com",
            password_hash="unused",
            name="Tenant A Affiliate",
            country="US",
        )
        account_b = AffiliateAccount(
            email="event-tenant-b@example.com",
            password_hash="unused",
            name="Tenant B Affiliate",
            country="US",
        )
        db.add_all([tenant_b, account_a, account_b])
        await db.flush()

        affiliate_a = Affiliate(
            affiliate_account_id=account_a.id,
            tenant_id=tenant.id,
        )
        affiliate_b = Affiliate(
            affiliate_account_id=account_b.id,
            tenant_id=tenant_b.id,
        )
        db.add_all([affiliate_a, affiliate_b])
        await db.flush()

        campaign_a = Campaign(
            affiliate_id=affiliate_a.id,
            tenant_id=tenant.id,
            tracking_code="event-tenant-a-code",
            landing_url="https://example.com/a",
        )
        campaign_b = Campaign(
            affiliate_id=affiliate_b.id,
            tenant_id=tenant_b.id,
            tracking_code="event-tenant-b-code",
            landing_url="https://example.com/b",
        )
        db.add_all([campaign_a, campaign_b])
        await db.commit()
        tenant_b_id = str(tenant_b.id)

    event_a = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": event_id,
            "type": "click",
            "tracking_code": "event-tenant-a-code",
            "customer_id": "tenant-a-private-customer",
        },
    )
    event_b = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": tenant_b_api_key},
        json={
            "event_id": event_id,
            "type": "click",
            "tracking_code": "event-tenant-b-code",
            "customer_id": "tenant-b-customer",
        },
    )

    assert event_a.status_code == 200
    assert event_b.status_code == 200
    assert event_b.json()["tenant_id"] == tenant_b_id
    assert event_b.json()["id"] != event_a.json()["id"]
    assert event_b.json()["customer_id"] == "tenant-b-customer"

    async with async_session() as db:
        count = await db.scalar(
            select(func.count(Event.id)).where(Event.event_id == event_id)
        )
    assert count == 2
```

- [ ] **Step 2: Run the new test and confirm the expected failure**

Run from `backend/`, with `TEST_DATABASE_URL` set to the approved disposable test database:

```bash
uv run pytest tests/test_events.py::test_event_idempotency_is_scoped_to_tenant -v
```

Expected before the fix: FAIL because tenant B receives the already-stored tenant A event (tenant ID/customer ID are wrong and only one row exists). Do not proceed if the command targets an unverified database.

- [ ] **Step 3: Extend the existing sale test to assert retry idempotency**

In `test_event_ingestion`, keep the existing invite/campaign setup and replace the inline sale payload with a reusable payload; send it twice and assert the response ID is unchanged. After both requests, assert exactly one commission is associated with that event:

Add `import uuid` to the test module imports. Replace the inline sale payload and request with this code:

```python
    sale_payload = {
        "event_id": "sale-1",
        "type": "sale",
        "campaign_id": campaign_id,
        "customer_id": "cust-1",
        "amount": 100.0,
        "currency": "USD",
        "payment_sequence": 1,
        "good_date": "2026-09-09",
        "payment_record_id": "pay-1",
    }
    sale = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json=sale_payload,
    )
    assert sale.status_code == 200
    assert sale.json()["type"] == "sale"

    retry = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json=sale_payload,
    )
    assert retry.status_code == 200
    assert retry.json()["id"] == sale.json()["id"]

    async with async_session() as db:
        commission_count = await db.scalar(
            select(func.count(Commission.id)).where(
                Commission.event_id == uuid.UUID(sale.json()["id"])
            )
        )
    assert commission_count == 1
```

- [ ] **Step 4: Re-run the focused event tests before implementation**

Run from `backend/` with the approved disposable `TEST_DATABASE_URL`:

```bash
uv run pytest tests/test_events.py -v
```

Expected before implementation: the cross-tenant test fails; the existing event and same-tenant retry checks pass. Record that failure as the regression proof.

### Task 2: Enforce the tenant-scoped database and service boundary

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/services/event.py`
- Create: `backend/alembic/versions/c2d3e4f5a6b7_tenant_scoped_event_idempotency.py`
- Test: `backend/tests/test_events.py`

- [ ] **Step 1: Add the composite constraint to the ORM model**

In `Event` in `backend/app/db/models.py`, add the named table constraint and remove `unique=True, index=True` from `event_id`:

```python
class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "event_id",
            name="uq_events_tenant_id_event_id",
        ),
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String, nullable=False)
```

Leave the rest of the model unchanged.

- [ ] **Step 2: Scope the service lookup to the tenant and event ID**

Replace the existing lookup in `backend/app/services/event.py` with:

```python
    existing_result = await db.execute(
        select(Event).where(
            Event.tenant_id == tenant.id,
            Event.event_id == data.event_id,
        )
    )
```

Keep the existing return of `existing` and all event validation/creation behavior unchanged.

- [ ] **Step 3: Add the Alembic revision**

Create `backend/alembic/versions/c2d3e4f5a6b7_tenant_scoped_event_idempotency.py` with the current head as its parent. Upgrade removes the global index and adds the composite unique constraint. Downgrade checks for cross-tenant duplicate external IDs before restoring global uniqueness:

```python
"""scope event idempotency to tenant

Revision ID: c2d3e4f5a6b7
Revises: f7a8b9c0d123
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "f7a8b9c0d123"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_events_event_id", table_name="events")
    op.create_unique_constraint(
        "uq_events_tenant_id_event_id",
        "events",
        ["tenant_id", "event_id"],
    )


def downgrade() -> None:
    duplicate = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM events "
            "GROUP BY event_id HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate:
        raise RuntimeError(
            "Cannot restore global event_id uniqueness while cross-tenant duplicates exist"
        )

    op.drop_constraint(
        "uq_events_tenant_id_event_id",
        "events",
        type_="unique",
    )
    op.create_index("ix_events_event_id", "events", ["event_id"], unique=True)
```

- [ ] **Step 4: Run focused event and tracking tests**

Run from `backend/` with the approved disposable `TEST_DATABASE_URL`:

```bash
uv run pytest tests/test_events.py tests/test_tracking.py -v
```

Expected: PASS, including the new tenant-isolation assertion, same-tenant retry, and existing tracking flow.

- [ ] **Step 5: Commit the implementation change set**

After focused tests pass, inspect and commit only the four implementation files:

```bash
git add backend/app/db/models.py backend/app/services/event.py backend/tests/test_events.py backend/alembic/versions/c2d3e4f5a6b7_tenant_scoped_event_idempotency.py
git commit -m "Scope event idempotency to tenant"
```

### Task 3: Verify migration compatibility and the complete backend suite

**Files:**
- Verify: `backend/alembic/versions/c2d3e4f5a6b7_tenant_scoped_event_idempotency.py`
- Verify: `backend/tests/test_events.py`, `backend/tests/test_tracking.py`

- [ ] **Step 1: Verify the upgrade preserves existing events on a disposable migration database**

Only after confirming `AFFILIATE_MIGRATION_DATABASE_URL` points to a disposable PostgreSQL database, run from `backend/`:

```bash
DATABASE_URL="$AFFILIATE_MIGRATION_DATABASE_URL" uv run alembic upgrade f7a8b9c0d123
```

Seed two tenants and one event for tenant A in that disposable database:

```bash
psql "$AFFILIATE_MIGRATION_DATABASE_URL" <<'SQL'
INSERT INTO tenants (id, name, api_key_hash) VALUES
  ('00000000-0000-0000-0000-000000000001', 'migration-tenant-a', 'migration-key-a'),
  ('00000000-0000-0000-0000-000000000002', 'migration-tenant-b', 'migration-key-b');
INSERT INTO events (id, event_id, type, tenant_id) VALUES
  ('00000000-0000-0000-0000-000000000011', 'event-before-migration', 'click',
   '00000000-0000-0000-0000-000000000001');
SQL
```

Then run:

```bash
DATABASE_URL="$AFFILIATE_MIGRATION_DATABASE_URL" uv run alembic upgrade head
psql "$AFFILIATE_MIGRATION_DATABASE_URL" -c \
  "SELECT id, event_id, tenant_id FROM events WHERE event_id = 'event-before-migration';"
psql "$AFFILIATE_MIGRATION_DATABASE_URL" -c \
  "SELECT conname FROM pg_constraint WHERE conrelid = 'events'::regclass AND conname = 'uq_events_tenant_id_event_id';"
psql "$AFFILIATE_MIGRATION_DATABASE_URL" -c \
  "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema() AND tablename = 'events' AND indexname = 'ix_events_event_id';"
```

Confirm the event row is unchanged, the constraint query returns `uq_events_tenant_id_event_id`, and the final index query returns no rows.

- [ ] **Step 2: Verify the guarded downgrade with duplicate and non-duplicate data**

On that same disposable database, insert a second event with the same external `event_id` under tenant B:

```bash
psql "$AFFILIATE_MIGRATION_DATABASE_URL" <<'SQL'
INSERT INTO events (id, event_id, type, tenant_id) VALUES
  ('00000000-0000-0000-0000-000000000012', 'event-before-migration', 'click',
   '00000000-0000-0000-0000-000000000002');
SQL
```

Run the downgrade command and confirm it exits unsuccessfully with `Cannot restore global event_id uniqueness while cross-tenant duplicates exist`. Query `pg_constraint` again to confirm the composite constraint remains intact. Delete only the second fixture event from this disposable database, rerun the downgrade, and confirm it succeeds and restores the unique `ix_events_event_id` index:

```bash
psql "$AFFILIATE_MIGRATION_DATABASE_URL" -c \
  "DELETE FROM events WHERE id = '00000000-0000-0000-0000-000000000012';"
DATABASE_URL="$AFFILIATE_MIGRATION_DATABASE_URL" uv run alembic downgrade f7a8b9c0d123
psql "$AFFILIATE_MIGRATION_DATABASE_URL" -c \
  "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = current_schema() AND tablename = 'events' AND indexname = 'ix_events_event_id';"
```

Do not run these data-changing steps against any shared or data-retaining database.

- [ ] **Step 3: Run the complete backend test suite**

Run from `backend/` with `TEST_DATABASE_URL` still explicitly set to the approved disposable test database:

```bash
uv run pytest tests/ -v
```

Expected: all backend tests pass. If failures occur, stop and report the exact failing tests before broadening scope.

- [ ] **Step 4: Update the roadmap only after all acceptance criteria pass**

In `docs/superpowers/plans/2026-09-30-affiliate-service-next-phase-execution-plan.md`, check only the completed Workstream 0.1 implementation steps and acceptance status. Do not check or change any other P0/P1/P2 workstream or resolve tax/attribution blockers by assumption.

- [ ] **Step 5: Review final changes**

Run:

```bash
git status --short --branch
git diff --check
git diff
```

Confirm the roadmap is the only untracked user-provided file unless it has explicitly been added to the change set, and confirm no payout/tax/attribution behavior changed.

## Acceptance Criteria

- A same-tenant repeat returns the original event and does not add a second commission.
- Another tenant may use the same `event_id` and receives its own event, with no details from the first tenant in the response.
- A database unique constraint enforces `(tenant_id, event_id)`.
- Migration upgrade preserves representative existing rows; downgrade restores global uniqueness only when no cross-tenant duplicates exist and otherwise fails without altering data.
- Focused event/tracking tests and the full backend suite pass on a disposable test database.
