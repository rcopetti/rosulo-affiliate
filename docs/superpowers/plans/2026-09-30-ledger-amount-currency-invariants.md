# Ledger Amount and Currency Invariants Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make financial calculations and stored amounts exact, keep every aggregate currency-scoped, and retain provider events whose currency is not yet enabled for affiliate commissions.

**Architecture:** Use Python `Decimal` and PostgreSQL `NUMERIC` for financial calculations and persistence. USD, EUR, and BRL are the current commission/payout currencies; each has two fractional digits. Preserve the existing numeric JSON amount fields, add per-currency balance responses, and never sum amounts from different currencies. Provider events with valid but unsupported currency codes remain stored and visibly held from commission generation.

**Tech Stack:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL, pytest, React, TypeScript, Vitest.

---

## File Map

- Create `backend/app/core/money.py`: Decimal parsing, currency normalization, supported-currency metadata, and half-up quantization.
- Modify `backend/app/db/models.py`: use Numeric for financial values and add `Event.commission_status`.
- Create `backend/alembic/versions/d4e5f6a7b8c9_ledger_amount_currency_invariants.py`: fail-closed data checks and Float-to-Numeric migration.
- Modify `backend/app/schemas/event.py`, `backend/app/schemas/commission.py`, `backend/app/schemas/payout.py`, `backend/app/schemas/contract.py`, and `backend/app/schemas/dashboard.py`: parse money/percentages as Decimal internally, preserve numeric JSON response fields, and add currency-scoped balance fields.
- Modify `backend/app/services/event.py`, `backend/app/services/commission.py`, `backend/app/services/tax.py`, `backend/app/services/payment_record.py`, `backend/app/services/payout.py`, `backend/app/services/dashboard.py`, `backend/app/services/contract.py`, and `backend/app/services/affiliate_account.py`: use Decimal arithmetic and currency-aware selection/aggregation.
- Create `backend/app/services/balance.py`: shared currency-scoped affiliate balance projection used by the balance route and dashboard.
- Modify `backend/app/api/v1/affiliate/balance.py`, `backend/app/api/v1/affiliate/payouts.py`, `backend/app/api/v1/public/events.py`, and `backend/app/api/v1/public/webhooks.py`: expose per-currency balances, require a payout currency, and parse incoming amounts as Decimal.
- Modify `backend/tests/test_commission.py`, `backend/tests/test_dashboard.py`, `backend/tests/test_events.py`, `backend/tests/test_payout.py`, and `backend/tests/test_tax.py`; create `backend/tests/test_money.py`, `backend/tests/test_money_models.py`, and `backend/tests/test_balance.py`.
- Modify `frontend/src/api/types.ts` (including `Event.commission_status`), `frontend/src/api/affiliate/payouts.ts`, `frontend/src/components/affiliate/BalanceSummary.tsx`, `frontend/src/components/affiliate/SalesBySequenceChart.tsx`, `frontend/src/components/admin/CommissionLiability.tsx`, `frontend/src/pages/affiliate/BalancePage.tsx`, `frontend/src/pages/affiliate/RequestPayoutPage.tsx`, and `frontend/src/pages/affiliate/DashboardPage.tsx`; create `frontend/src/components/affiliate/CurrencyBalances.tsx` and `frontend/src/tests/components/CurrencyBalances.test.tsx`.
- Update only Workstream 0.5’s checkboxes/status in `docs/superpowers/plans/2026-09-30-affiliate-service-next-phase-execution-plan.md` after all acceptance criteria pass.

## Database Safety Gate

`backend/tests/conftest.py` drops and recreates all tables in its configured test database at session startup. Use `TEST_DATABASE_URL` only when it points at a disposable database; otherwise verify the repository fallback `<DATABASE_URL database>_test` (currently `rosulo_affiliate_test`) is disposable. Never point pytest at the dev database itself.

Migration smoke checks must use a separate disposable PostgreSQL database named with suffix `_w05_migration_test`. Derive its URL from local settings without printing credentials. If that target already exists, stop and ask before modifying it; never drop or overwrite it. Do not run migration/data checks against production or a data-retaining database.

## Scope Boundary

As explicitly deferred to Workstream 0.2, W0.5 does not change the existing inbound `PaymentRecord` commission-availability lookup. That lookup remains keyed by external payment ID without tenant/currency matching and is not safe for production settlement. W0.2 must replace it before real payouts are enabled.

### Task 0: Verify branch and test baseline

**Files:** none

- [ ] **Step 1: Confirm the feature branch starts clean**

Run from the repository root:

```bash
git status --short --branch
git branch --show-current
```

Expected: current branch is `feature/ledger-amount-currency-invariants`; only the committed W0.5 spec/plan documentation is present.

- [ ] **Step 2: Run the backend baseline on the disposable test database**

Run from `backend/` using the approved disposable `TEST_DATABASE_URL` or the repository-derived `_test` database:

```bash
uv run pytest tests/ -v
```

Expected: baseline backend suite passes before any code changes. Stop if the suite is failing or if the database target is not disposable.

### Task 1: Establish exact money helpers with failing unit tests

**Files:**
- Create: `backend/tests/test_money.py`
- Create: `backend/app/core/money.py`

- [ ] **Step 1: Add failing tests for Decimal conversion, rounding, and currency handling**

Create `backend/tests/test_money.py`:

```python
from decimal import Decimal

import pytest

from app.core.money import (
    is_supported_currency,
    normalize_currency_code,
    normalize_provider_amount,
    quantize_ledger_amount,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1.004", Decimal("1.00")),
        ("1.005", Decimal("1.01")),
        ("-1.005", Decimal("-1.01")),
        ("1.999", Decimal("2.00")),
    ],
)
def test_provider_amount_uses_half_up_two_decimal_normalization(value, expected):
    assert normalize_provider_amount(value) == expected


def test_ledger_amount_requires_enabled_currency():
    assert quantize_ledger_amount("10.005", "USD") == Decimal("10.01")
    assert is_supported_currency("EUR")
    assert not is_supported_currency("XYZ")
    with pytest.raises(ValueError, match="Unsupported ledger currency"):
        quantize_ledger_amount("10.00", "XYZ")


def test_currency_codes_are_normalized_without_an_allowlist_rejection():
    assert normalize_currency_code(" xyz ") == "XYZ"
    assert normalize_currency_code("brl") == "BRL"
```

- [ ] **Step 2: Run the new test and confirm it fails for the missing helper**

Run from `backend/`:

```bash
uv run pytest tests/test_money.py -v
```

Expected: FAIL because `app.core.money` does not exist yet. Pytest still runs the session-autouse database fixture, so the disposable-database safety gate applies even to this unit test.

- [ ] **Step 3: Implement the shared money helper**

Create `backend/app/core/money.py`:

```python
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SUPPORTED_CURRENCY_EXPONENTS = {"USD": 2, "EUR": 2, "BRL": 2}
_PROVIDER_EXPONENT = 2


def decimal_value(value: Decimal | str | float) -> Decimal:
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid monetary amount") from exc
    if not amount.is_finite():
        raise ValueError("Monetary amount must be finite")
    return amount


def normalize_currency_code(currency: str) -> str:
    code = currency.strip().upper()
    if len(code) != 3 or not code.isascii() or not code.isalpha():
        raise ValueError("Currency must be a three-letter code")
    return code


def is_supported_currency(currency: str) -> bool:
    return normalize_currency_code(currency) in SUPPORTED_CURRENCY_EXPONENTS


def _quantum(exponent: int) -> Decimal:
    return Decimal(1).scaleb(-exponent)


def normalize_provider_amount(value: Decimal | str | float) -> Decimal:
    return decimal_value(value).quantize(
        _quantum(_PROVIDER_EXPONENT), rounding=ROUND_HALF_UP
    )


def quantize_ledger_amount(
    value: Decimal | str | float, currency: str
) -> Decimal:
    code = normalize_currency_code(currency)
    exponent = SUPPORTED_CURRENCY_EXPONENTS.get(code)
    if exponent is None:
        raise ValueError("Unsupported ledger currency")
    return decimal_value(value).quantize(_quantum(exponent), rounding=ROUND_HALF_UP)
```

- [ ] **Step 4: Re-run the helper tests**

Run from `backend/`:

```bash
uv run pytest tests/test_money.py -v
```

Expected: PASS for positive and negative half-up boundaries, supported ledger precision, and provider-code normalization independent of ledger support.

- [ ] **Step 5: Commit the helper and its tests**

```bash
git add backend/app/core/money.py backend/tests/test_money.py
git commit -m "Add Decimal currency helpers"
```

### Task 2: Prove Decimal model/calculation behavior before changing models

**Files:**
- Create: `backend/tests/test_money_models.py`
- Modify: `backend/tests/test_commission.py`
- Modify: `backend/tests/test_tax.py`

- [ ] **Step 1: Add ORM precision assertions**

Create `backend/tests/test_money_models.py` with these imports and test:

```python
from sqlalchemy import Numeric

from app.db.models import (
    Commission,
    Event,
    PaymentRecord,
    Payout,
    PayoutCommission,
    Term,
)
```

Add this test:

```python
def test_financial_model_columns_use_expected_numeric_precision():
    money_columns = (
        Event.__table__.c.amount,
        PaymentRecord.__table__.c.amount,
        Commission.__table__.c.gross_amount,
        Commission.__table__.c.withholding_amount,
        Commission.__table__.c.net_amount,
        Payout.__table__.c.requested_amount,
        Payout.__table__.c.approved_amount,
        Payout.__table__.c.withholding_total,
        Payout.__table__.c.paypal_fees,
        Payout.__table__.c.net_paid,
        PayoutCommission.__table__.c.amount,
        Term.__table__.c.minimum_threshold,
    )
    for column in money_columns:
        assert type(column.type) is Numeric
        assert column.type.precision == 20
        assert column.type.scale == 2

    assert type(Term.__table__.c.commission_percent.type) is Numeric
    assert Term.__table__.c.commission_percent.type.precision == 9
    assert Term.__table__.c.commission_percent.type.scale == 6
```

- [ ] **Step 2: Add a commission half-up regression using the existing integration fixture**

In `backend/tests/test_commission.py::test_sale_generates_commission`, pass an explicit threshold in the admin invite request:

```python
json={
    "email": "commission@example.com",
    "contract_terms": [
        {
            "commission_percent": 10.0,
            "payment_sequence": 1,
            "minimum_threshold": 2.05,
        }
    ],
}
```

Change the existing duplicate USD sale payload to `amount: 2.05` and `currency: "USD"`; the existing test posts it twice and asserts there is still one Commission. Change the gross assertion to:

```python
assert comms.json()[0]["gross_amount"] == 0.21
```

Then post a distinct EUR sale on the same campaign:

```python
eur_sale = await client.post(
    "/api/v1/events",
    headers={"X-API-Key": "test-api-key"},
    json={
        "event_id": "commission-eur-below-threshold",
        "type": "sale",
        "campaign_id": campaign_id,
        "customer_id": "cust-eur",
        "amount": 2.04,
        "currency": "EUR",
        "payment_sequence": 1,
        "good_date": str(date.today()),
    },
)
assert eur_sale.status_code == 200
```

Fetch commissions again and assert there is still only the USD commission. This verifies the minimum threshold is interpreted in the event's own currency without FX conversion. The USD value is `2.05 × 10% = 0.205`; binary-float `round()` yields `0.20`, while half-up Decimal quantization must yield `0.21`.

- [ ] **Step 3: Change the existing tax unit test to use Decimal values**

In `backend/tests/test_tax.py`, add `from decimal import Decimal` and replace the test body with:

```python
@pytest.mark.asyncio
async def test_tax_withholding():
    us = AffiliateAccount(tax_status="us_person", backup_withholding_required=False)
    assert apply_tax(us, Decimal("100.00")) == (
        Decimal("100.00"),
        Decimal("0.00"),
        Decimal("100.00"),
    )

    us_backup = AffiliateAccount(tax_status="us_person", backup_withholding_required=True)
    assert apply_tax(us_backup, Decimal("100.00"))[1] == Decimal("24.00")

    non_us = AffiliateAccount(tax_status="non_us_person", backup_withholding_required=False)
    assert apply_tax(non_us, Decimal("100.00"))[1] == Decimal("30.00")
```

- [ ] **Step 4: Run the targeted tests and confirm expected failures**

Run from `backend/` with the approved disposable test database:

```bash
uv run pytest tests/test_money_models.py tests/test_commission.py tests/test_tax.py -v
```

Expected before implementation: ORM assertions fail because the columns are Float; the 2.05 sale at 10% yields 0.20 rather than the required half-up 0.21; Decimal tax inputs are rejected by the float-only calculation.

### Task 3: Convert financial columns and commission calculations to Decimal/Numeric

**Files:**
- Modify: `backend/app/db/models.py`
- Modify: `backend/app/schemas/event.py`
- Modify: `backend/app/schemas/commission.py`
- Modify: `backend/app/schemas/contract.py`
- Modify: `backend/app/services/commission.py`
- Modify: `backend/app/services/tax.py`
- Modify: `backend/app/services/contract.py`
- Modify: `backend/app/services/affiliate_account.py`
- Modify: `backend/app/services/payment_record.py`
- Modify: `backend/app/api/v1/public/webhooks.py`
- Create: `backend/alembic/versions/d4e5f6a7b8c9_ledger_amount_currency_invariants.py`

- [ ] **Step 1: Change financial ORM columns to Numeric**

In `backend/app/db/models.py`, import `Decimal` and SQLAlchemy `Numeric`; remove `Float` if no Float columns remain. Change `Event.amount`, `PaymentRecord.amount`, Commission `gross_amount`/`withholding_amount`/`net_amount`, Payout `requested_amount`/`approved_amount`/`withholding_total`/`paypal_fees`/`net_paid`, PayoutCommission `amount`, and Term `minimum_threshold` to `Numeric(20, 2)`. Change `Term.commission_percent` to `Numeric(9, 6)`. Keep `Term.minimum_threshold` nullable and preserve existing nullability for other columns. Use `Decimal("0.00")` defaults for money columns.

- [ ] **Step 2: Update schemas to parse money as Decimal while preserving numeric JSON responses**

In `backend/app/schemas/event.py`, import `Decimal`, use `amount: Decimal = Decimal("0.00")` in `EventCreate`, retain `EventOut.amount: float`, and add `commission_status: str | None = None`. In `backend/app/schemas/commission.py`, keep output amount fields as `float`. In `backend/app/schemas/contract.py`, use Decimal for `TermBase.commission_percent`, `TermBase.minimum_threshold`, and `TermUpdate` equivalents; keep `TermOut` monetary/rate values as float response fields.

- [ ] **Step 3: Use Decimal for commission, tax, and contract calculations**

Update `backend/app/services/commission.py` to convert percentage values with `Decimal(str(applicable.commission_percent))`, multiply Decimal event amounts, and quantize before storing gross/net values:

```python
gross = quantize_ledger_amount(
    event.amount * Decimal(str(applicable.commission_percent)) / Decimal(100),
    event.currency,
)
_, withholding, net = apply_tax(account, gross)
```

Update `backend/app/services/tax.py` to use Decimal rates `Decimal("0.24")`, `Decimal("0.30")`, and `Decimal("0.00")`; quantize withholding/net with half-up. Do not change the rates or tax-status policy. Update `backend/app/services/contract.py` to convert incoming numeric contract values with `decimal_value` before assigning them. In `backend/app/services/affiliate_account.py`, convert numeric values in the invite `contract_terms` JSON with `decimal_value` before creating `Term` rows. Keep `create_reversal` semantics unchanged, converting its numeric literals/results to Decimal only; end-to-end refund/chargeback creation is outside W0.5.

- [ ] **Step 4: Parse the current tenant payment webhook amount as Decimal**

In `backend/app/services/payment_record.py`, accept Decimal for `amount`. In `backend/app/api/v1/public/webhooks.py`, replace `float(payload.get("amount", 0))` with `decimal_value(payload.get("amount", 0))`. Keep the incoming `PaymentRecord` meaning unchanged in W0.5; Workstream 0.2 will repurpose it for manual merchant-to-affiliate settlement.

- [ ] **Step 5: Add the Alembic migration in the same change set**

Create `backend/alembic/versions/d4e5f6a7b8c9_ledger_amount_currency_invariants.py` with the following core migration implementation. Add the full preflight queries and conversion list exactly as shown; do not infer or coerce data outside these rules:

```python
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY_COLUMNS = (
    ("events", "amount"),
    ("payment_records", "amount"),
    ("commissions", "gross_amount"),
    ("commissions", "withholding_amount"),
    ("commissions", "net_amount"),
    ("payouts", "requested_amount"),
    ("payouts", "approved_amount"),
    ("payouts", "withholding_total"),
    ("payouts", "paypal_fees"),
    ("payouts", "net_paid"),
    ("payout_commissions", "amount"),
)


def _assert_no_rows(query: str, message: str) -> None:
    if op.get_bind().execute(sa.text(query)).first():
        raise RuntimeError(message)


def _preflight() -> None:
    for table, column in MONEY_COLUMNS:
        _assert_no_rows(
            f"SELECT 1 FROM {table} WHERE {column} IS NULL LIMIT 1",
            f"Cannot migrate {table}.{column}: NULL monetary values require review",
        )
    for table in ("events", "payment_records", "commissions", "payouts"):
        _assert_no_rows(
            f"SELECT 1 FROM {table} WHERE currency IS NULL LIMIT 1",
            f"Cannot migrate {table}: NULL currency values require review",
        )

    _assert_no_rows(
        "SELECT 1 FROM commissions WHERE currency NOT IN ('USD', 'EUR', 'BRL') LIMIT 1",
        "Cannot migrate commissions with currencies outside USD/EUR/BRL",
    )
    _assert_no_rows(
        "SELECT 1 FROM payouts WHERE currency NOT IN ('USD', 'EUR', 'BRL') LIMIT 1",
        "Cannot migrate payouts with currencies outside USD/EUR/BRL",
    )
    _assert_no_rows(
        "SELECT 1 FROM commissions c JOIN events e ON e.id = c.event_id "
        "WHERE c.currency IS DISTINCT FROM e.currency LIMIT 1",
        "Cannot migrate commissions whose currency differs from their source event",
    )
    _assert_no_rows(
        "SELECT 1 FROM payout_commissions pc "
        "JOIN commissions c ON c.id = pc.commission_id "
        "JOIN payouts p ON p.id = pc.payout_id "
        "WHERE p.currency IS DISTINCT FROM c.currency LIMIT 1",
        "Cannot migrate payouts whose currency differs from a linked commission",
    )
    _assert_no_rows(
        "SELECT 1 FROM payout_commissions pc "
        "JOIN commissions c ON c.id = pc.commission_id "
        "GROUP BY pc.payout_id HAVING count(DISTINCT c.currency) > 1 LIMIT 1",
        "Cannot migrate a payout linked to commissions in multiple currencies",
    )


def upgrade() -> None:
    _preflight()
    for table, column in MONEY_COLUMNS:
        op.alter_column(
            table,
            column,
            existing_type=sa.Float(),
            type_=sa.Numeric(20, 2),
            postgresql_using=f"round({column}::numeric, 2)",
        )
    op.alter_column(
        "terms",
        "minimum_threshold",
        existing_type=sa.Float(),
        type_=sa.Numeric(20, 2),
        postgresql_using="round(minimum_threshold::numeric, 2)",
    )
    op.alter_column(
        "terms",
        "commission_percent",
        existing_type=sa.Float(),
        type_=sa.Numeric(9, 6),
        postgresql_using="round(commission_percent::numeric, 6)",
    )
    op.add_column("events", sa.Column("commission_status", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("events", "commission_status")
    op.alter_column(
        "terms",
        "commission_percent",
        existing_type=sa.Numeric(9, 6),
        type_=sa.Float(),
        postgresql_using="commission_percent::double precision",
    )
    op.alter_column(
        "terms",
        "minimum_threshold",
        existing_type=sa.Numeric(20, 2),
        type_=sa.Float(),
        postgresql_using="minimum_threshold::double precision",
    )
    for table, column in reversed(MONEY_COLUMNS):
        op.alter_column(
            table,
            column,
            existing_type=sa.Numeric(20, 2),
            type_=sa.Float(),
            postgresql_using=f"{column}::double precision",
        )
```

- [ ] **Step 6: Run the targeted test group and commit Task 3**

Run from `backend/`:

```bash
uv run pytest tests/test_money.py tests/test_money_models.py tests/test_commission.py tests/test_tax.py tests/test_events.py -v
```

Expected: PASS; model precision, Decimal commission/tax behavior, and current event ingestion all work on the ORM-created disposable test schema.

Commit only the Task 3 files:

```bash
git add backend/app/db/models.py backend/app/schemas/event.py backend/app/schemas/commission.py backend/app/schemas/contract.py backend/app/services/commission.py backend/app/services/tax.py backend/app/services/contract.py backend/app/services/affiliate_account.py backend/app/services/payment_record.py backend/app/api/v1/public/webhooks.py backend/alembic/versions/d4e5f6a7b8c9_ledger_amount_currency_invariants.py backend/tests/test_money.py backend/tests/test_money_models.py backend/tests/test_commission.py backend/tests/test_tax.py
git commit -m "Store ledger amounts with decimal precision"
```

### Task 4: Add currency-aware event commission handling

**Files:**
- Modify: `backend/app/api/v1/public/events.py`
- Modify: `backend/app/services/event.py`
- Modify: `backend/app/services/commission.py`
- Modify: `backend/app/schemas/event.py`
- Modify: `backend/tests/test_events.py`

- [ ] **Step 1: Add a failing unsupported-currency API test**

Extend `test_event_ingestion` with a `monkeypatch` parameter. Add these imports if absent:

```python
import uuid
from datetime import date

from sqlalchemy import func, select

from app.core import money
from app.db.models import Commission
from app.db.session import async_session
```

After `campaign_id` is available, append:

```python
    unsupported_payload = {
        "event_id": "unsupported-currency-sale",
        "type": "sale",
        "campaign_id": campaign_id,
        "customer_id": "unsupported-currency-customer",
        "amount": 10.005,
        "currency": "XYZ",
        "payment_sequence": 1,
        "good_date": str(date.today()),
        "payment_record_id": "unsupported-currency-payment",
    }
    unsupported = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json=unsupported_payload,
    )
    assert unsupported.status_code == 200
    assert unsupported.json()["currency"] == "XYZ"
    assert unsupported.json()["amount"] == 10.01
    assert unsupported.json()["commission_status"] == "currency_unsupported"

    event_uuid = uuid.UUID(unsupported.json()["id"])
    async with async_session() as db:
        commission_count = await db.scalar(
            select(func.count(Commission.id)).where(Commission.event_id == event_uuid)
        )
    assert commission_count == 0

    monkeypatch.setitem(money.SUPPORTED_CURRENCY_EXPONENTS, "XYZ", 2)
    replay = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json=unsupported_payload,
    )
    assert replay.status_code == 200
    assert replay.json()["commission_status"] is None

    async with async_session() as db:
        commission_count = await db.scalar(
            select(func.count(Commission.id)).where(Commission.event_id == event_uuid)
        )
    assert commission_count == 1

- [ ] **Step 2: Run the event test and confirm the expected failure**

Run from `backend/`:

```bash
uv run pytest tests/test_events.py::test_event_ingestion -v
```

Expected before implementation: the response has no `commission_status`, and the current service attempts to calculate commissions without checking whether the currency is enabled.

- [ ] **Step 3: Implement the currency hold and replay behavior**

In the sale commission path, check `is_supported_currency(event.currency)` before calculating a Commission. For unsupported currency, set `event.commission_status = "currency_unsupported"`, commit that event state, and return without creating a Commission. For a supported currency, create the Commission exactly once and clear the blocked state. Keep the route’s tenant-scoped event idempotency and commission-count check so replaying the event after currency support is added can create the missing Commission.

- [ ] **Step 4: Re-run the event tests**

Run from `backend/`:

```bash
uv run pytest tests/test_events.py -v
```

Expected: PASS for stored unsupported-currency events, visible blocked state, and exactly-once commission creation after support is enabled.

- [ ] **Step 5: Commit the unsupported-currency handling**

```bash
git add backend/app/services/event.py backend/app/services/commission.py backend/app/api/v1/public/events.py backend/tests/test_events.py
git commit -m "Hold unsupported-currency commissions for replay"
```

### Task 5: Centralize currency-scoped balances and dashboard aggregates

**Files:**
- Create: `backend/app/services/balance.py`
- Modify: `backend/app/api/v1/affiliate/balance.py`
- Modify: `backend/app/services/dashboard.py`
- Modify: `backend/app/schemas/dashboard.py`
- Create: `backend/tests/test_balance.py`
- Modify: `backend/tests/test_dashboard.py`

- [ ] **Step 1: Add a failing pure balance-projection test**

Create `backend/tests/test_balance.py`:

```python
from decimal import Decimal

from app.services.balance import build_balances


def test_build_balances_groups_currencies_and_keeps_reversal_separate():
    balances = build_balances(
        [
            ("USD", "pending", Decimal("1.00"), Decimal("9.00")),
            ("USD", "available", Decimal("0.00"), Decimal("5.00")),
            ("USD", "paid", Decimal("0.00"), Decimal("20.00")),
            ("USD", "reversed", Decimal("0.00"), Decimal("-3.00")),
            ("EUR", "available", Decimal("0.00"), Decimal("7.00")),
        ]
    )

    by_currency = {balance["currency"]: balance for balance in balances}
    assert by_currency["USD"]["earned"] == Decimal("31.00")
    assert by_currency["USD"]["pending"] == Decimal("9.00")
    assert by_currency["USD"]["tax_retained"] == Decimal("1.00")
    assert by_currency["USD"]["available"] == Decimal("5.00")
    assert by_currency["USD"]["paid"] == Decimal("20.00")
    assert by_currency["USD"]["reversal_total"] == Decimal("3.00")
    assert by_currency["USD"]["debt"] == Decimal("3.00")
    assert by_currency["EUR"]["earned"] == Decimal("7.00")
    assert by_currency["EUR"]["available"] == Decimal("7.00")
```

- [ ] **Step 2: Run the test and confirm it fails**

Run from `backend/`:

```bash
uv run pytest tests/test_balance.py -v
```

Expected: FAIL because the shared balance projection does not exist.

- [ ] **Step 3: Implement the shared Decimal balance projection**

Create `backend/app/services/balance.py` with a pure row projector and async SQL query:

```python
from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Commission

ZERO = Decimal("0.00")


def build_balances(rows) -> list[dict]:
    balances = defaultdict(
        lambda: {
            "earned": ZERO,
            "pending": ZERO,
            "available": ZERO,
            "paid": ZERO,
            "tax_retained": ZERO,
            "reversal_total": ZERO,
        }
    )
    for currency, status, withholding, net in rows:
        balance = balances[currency]
        net_amount = net or ZERO
        balance["earned"] += net_amount
        balance["tax_retained"] += withholding or ZERO
        if status in {"pending", "available", "paid"}:
            balance[status] += net_amount
        if status == "reversed" and net_amount < 0:
            balance["reversal_total"] += abs(net_amount)

    return [
        {
            "currency": currency,
            **amounts,
            "debt": amounts["reversal_total"],
        }
        for currency, amounts in sorted(balances.items())
    ]


async def get_balances(db: AsyncSession, affiliate_id: UUID) -> list[dict]:
    result = await db.execute(
        select(
            Commission.currency,
            Commission.status,
            func.sum(Commission.withholding_amount),
            func.sum(Commission.net_amount),
        )
        .where(Commission.affiliate_id == affiliate_id)
        .group_by(Commission.currency, Commission.status)
    )
    return build_balances(result.all())
```

Keep these results as Decimal until they pass through the Pydantic response model. Add this compatibility helper to `balance.py`:

```python
def add_legacy_balance_fields(balances: list[dict]) -> dict:
    response = {"balances_by_currency": balances}
    if len(balances) == 1:
        response.update(balances[0])
    elif not balances:
        response.update(
            {
                "currency": "USD",
                "earned": 0.0,
                "pending": 0.0,
                "available": 0.0,
                "paid": 0.0,
                "tax_retained": 0.0,
                "reversal_total": 0.0,
                "debt": 0.0,
            }
        )
    else:
        response.update(
            {
                "currency": None,
                "earned": None,
                "pending": None,
                "available": None,
                "paid": None,
                "tax_retained": None,
                "reversal_total": None,
                "debt": None,
            }
        )
    return response
```

Do not sum amounts across currencies.

- [ ] **Step 4: Update balance and dashboard API projections**

Use `get_balances` and `add_legacy_balance_fields` in `/api/v1/affiliate/balance`, and set `response_model=BalanceOut` so Decimal values convert to the existing numeric JSON fields at serialization. Use the same projection in `affiliate_dashboard`. Always return `balances_by_currency`. For exactly one currency populate legacy flat values from that entry; for multiple currencies set legacy flat amounts and `currency` to `None`; for no commissions return an empty list and zero/USD legacy values.

Group affiliate sales-by-sequence by `(payment_sequence, Commission.currency)` and tenant commission liability by `(month, Commission.currency)`. Add currency fields to `BalanceOut`, `SalesBySequencePoint`, `CommissionLiabilityRow`, `AffiliateDashboardOut`, and `TenantDashboardOut`. Keep all dashboard service aggregation in Decimal; remove `float()` conversions from aggregate/service code and let the Pydantic response models convert at the API boundary.

- [ ] **Step 5: Add API-level grouping assertions and run dashboard tests**

Extend `test_dashboards` after campaign creation to post these sales:

```python
    for event_id, currency in (("dash-sale-usd", "USD"), ("dash-sale-eur", "EUR")):
        response = await client.post(
            "/api/v1/events",
            headers={"X-API-Key": "test-api-key"},
            json={
                "event_id": event_id,
                "type": "sale",
                "campaign_id": campaign_id,
                "customer_id": f"customer-{currency.lower()}",
                "amount": 100.0,
                "currency": currency,
                "payment_sequence": 1,
                "good_date": str(date.today()),
            },
        )
        assert response.status_code == 200
```

After fetching `a_dash`, assert `set(row["currency"] for row in a_dash.json()["balance"]["balances_by_currency"]) == {"USD", "EUR"}`, the legacy top-level `earned` and `currency` are `None`, and `sales_by_sequence` contains separate USD/EUR rows. After fetching `t_dash`, assert `commission_liability` has separate USD/EUR rows for the same period.

Run from `backend/`:

```bash
uv run pytest tests/test_balance.py tests/test_dashboard.py -v
```

Expected: PASS for every per-currency balance and dashboard aggregate.

- [ ] **Step 6: Commit the currency-scoped balance projections**

```bash
git add backend/app/services/balance.py backend/app/api/v1/affiliate/balance.py backend/app/services/dashboard.py backend/app/schemas/dashboard.py backend/tests/test_balance.py backend/tests/test_dashboard.py
git commit -m "Group ledger balances by currency"
```

### Task 6: Scope payout requests and frontend views to one currency

**Files:**
- Modify: `backend/app/schemas/payout.py`
- Modify: `backend/app/api/v1/affiliate/payouts.py`
- Modify: `backend/app/services/payout.py`
- Modify: `backend/tests/test_payout.py`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/affiliate/payouts.ts`
- Modify: `frontend/src/components/affiliate/BalanceSummary.tsx`
- Modify: `frontend/src/components/affiliate/SalesBySequenceChart.tsx`
- Modify: `frontend/src/components/admin/CommissionLiability.tsx`
- Modify: `frontend/src/pages/affiliate/BalancePage.tsx`
- Modify: `frontend/src/pages/affiliate/RequestPayoutPage.tsx`
- Modify: `frontend/src/pages/affiliate/DashboardPage.tsx`
- Create: `frontend/src/components/affiliate/CurrencyBalances.tsx`
- Create: `frontend/src/tests/components/CurrencyBalances.test.tsx`

- [ ] **Step 1: Add the failing payout currency-selection test**

In `test_payout_flow`, after the existing USD sale/webhook, post a second sale and mark its matching tenant payment record paid:

```python
    eur_sale = await client.post(
        "/api/v1/events",
        headers={"X-API-Key": "test-api-key"},
        json={
            "event_id": "payout-sale-eur",
            "type": "sale",
            "campaign_id": campaign_id,
            "customer_id": "cust-eur",
            "amount": 100.0,
            "currency": "EUR",
            "payment_sequence": 1,
            "good_date": str(date.today()),
            "payment_record_id": "payout-pay-eur",
        },
    )
    assert eur_sale.status_code == 200
    await client.post(
        "/api/v1/webhooks/tenant",
        headers={"X-API-Key": "test-api-key"},
        json={
            "payment_record_id": "payout-pay-eur",
            "customer_id": "cust-eur",
            "amount": 100.0,
            "currency": "EUR",
            "sequence_number": 1,
            "status": "paid",
        },
    )
```

Change the payout request to send `json={"currency": "USD"}`. Assert its currency is USD and its `requested_amount` is 10.0 (not 20.0). Fetch the affiliate commissions and assert the EUR commission remains `available` while the USD commission is reserved.

- [ ] **Step 2: Run the payout test and confirm the expected failure**

Run from `backend/`:

```bash
uv run pytest tests/test_payout.py -v
```

Expected before implementation: `PayoutRequest` has no currency input and `request_payout` sums all available commissions while hard-coding USD.

- [ ] **Step 3: Require and apply payout currency selection**

Add `currency: str` to `PayoutRequest`. Pass it through the affiliate route to `request_payout(db, affiliate, currency)`. Validate it with `is_supported_currency`; select only available commissions matching the affiliate and currency; sum Decimal gross/withholding/net; set `Payout.currency` to the requested value. Do no FX conversion.

- [ ] **Step 4: Add a failing frontend per-currency rendering test**

Create `frontend/src/tests/components/CurrencyBalances.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { CurrencyBalances } from '@/components/affiliate/CurrencyBalances';
import { Balance } from '@/api/types';

const balance: Balance = {
  balances_by_currency: [
    {
      currency: 'USD', earned: 10, pending: 1, available: 2, paid: 7,
      tax_retained: 0, reversal_total: 0, debt: 0,
    },
    {
      currency: 'EUR', earned: 20, pending: 3, available: 4, paid: 13,
      tax_retained: 0, reversal_total: 0, debt: 0,
    },
  ],
  earned: null,
  pending: null,
  available: null,
  paid: null,
  tax_retained: null,
  reversal_total: null,
  debt: null,
  currency: null,
};

describe('CurrencyBalances', () => {
  it('renders balances separately without creating a combined total', () => {
    render(<CurrencyBalances balance={balance} />);
    expect(screen.getByRole('heading', { name: 'USD balance' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'EUR balance' })).toBeInTheDocument();
    expect(screen.getByText('$10.00')).toBeInTheDocument();
    expect(screen.getByText('€20.00')).toBeInTheDocument();
    expect(screen.queryByText('$30.00')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Run the frontend regression test and confirm it fails**

Run from `frontend/`:

```bash
npm run test -- src/tests/components/CurrencyBalances.test.tsx
```

Expected before implementation: `CurrencyBalances` does not exist.

- [ ] **Step 6: Update the frontend types and render one section per currency**

In the existing `Event` interface in `frontend/src/api/types.ts`, add `commission_status?: 'currency_unsupported' | null`. Add these currency types:

```typescript
export interface CurrencyBalance {
  currency: string;
  earned: number;
  pending: number;
  available: number;
  paid: number;
  tax_retained: number;
  reversal_total: number;
  debt: number;
}

export interface Balance {
  balances_by_currency: CurrencyBalance[];
  earned: number | null;
  pending: number | null;
  available: number | null;
  paid: number | null;
  tax_retained: number | null;
  reversal_total: number | null;
  debt: number | null;
  currency: string | null;
}
```

Add `currency: string` to sales-by-sequence and commission-liability row types. Create `frontend/src/components/affiliate/CurrencyBalances.tsx`:

```tsx
import { Balance, CurrencyBalance } from '@/api/types';
import { BalanceSummary } from '@/components/affiliate/BalanceSummary';
import { StatsCards } from '@/components/affiliate/StatsCards';

export function CurrencyBalances({ balance }: { balance: Balance }) {
  const currencies = balance.balances_by_currency.length
    ? balance.balances_by_currency
    : [
        {
          currency: balance.currency ?? 'USD',
          earned: balance.earned ?? 0,
          pending: balance.pending ?? 0,
          available: balance.available ?? 0,
          paid: balance.paid ?? 0,
          tax_retained: balance.tax_retained ?? 0,
          reversal_total: balance.reversal_total ?? 0,
          debt: balance.debt ?? 0,
        },
      ];

  return (
    <div className="space-y-6">
      {currencies.map((currencyBalance: CurrencyBalance) => (
        <section
          key={currencyBalance.currency}
          aria-labelledby={`balance-${currencyBalance.currency}`}
        >
          <h2 id={`balance-${currencyBalance.currency}`} className="text-lg font-semibold">
            {currencyBalance.currency} balance
          </h2>
          <StatsCards
            earned={currencyBalance.earned}
            pending={currencyBalance.pending}
            available={currencyBalance.available}
            paid={currencyBalance.paid}
            currency={currencyBalance.currency}
          />
          <BalanceSummary balance={currencyBalance} />
        </section>
      ))}
    </div>
  );
}
```

Change `BalanceSummary` to accept `CurrencyBalance` and label `reversal_total` as “Reversal total” instead of presenting the legacy `debt` alias as collectible debt. Use `<CurrencyBalances balance={balance} />` from `BalancePage` and `<CurrencyBalances balance={dashboard.balance} />` from `DashboardPage`. Group `dashboard.sales_by_sequence` by `row.currency`; render a labelled `Sales by sequence — USD`, `Sales by sequence — EUR`, or `Sales by sequence — BRL` chart for each group. Add a Currency column to `CommissionLiability`, format each value with its own `row.currency`, and use `${row.period}-${row.currency}` as its row key.

In `RequestPayoutPage`, create a `currency` state, derive options from `balance.balances_by_currency`, and render the existing Select with `label="Payout currency"`. Disable the request button until a currency is selected and display only that currency's available amount. Change `frontend/src/api/affiliate/payouts.ts` to `requestPayout(currency: string)` and post `{ currency }`, not an amount. Change `BalanceSummary` to accept `CurrencyBalance` and label `reversal_total` as “Reversal total” instead of presenting the legacy `debt` alias as collectible debt.

- [ ] **Step 7: Run frontend tests and build**

Run from `frontend/`:

```bash
npm run test
npm run build
```

Expected: all Vitest tests pass and TypeScript/Vite build succeeds.

- [ ] **Step 8: Commit currency-scoped payout requests and frontend views**

```bash
git add backend/app/schemas/payout.py backend/app/api/v1/affiliate/payouts.py backend/app/services/payout.py backend/tests/test_payout.py frontend/src/api/types.ts frontend/src/api/affiliate/payouts.ts frontend/src/components/affiliate/BalanceSummary.tsx frontend/src/components/affiliate/SalesBySequenceChart.tsx frontend/src/components/admin/CommissionLiability.tsx frontend/src/pages/affiliate/BalancePage.tsx frontend/src/pages/affiliate/RequestPayoutPage.tsx frontend/src/pages/affiliate/DashboardPage.tsx frontend/src/components/affiliate/CurrencyBalances.tsx frontend/src/tests/components/CurrencyBalances.test.tsx
git commit -m "Scope payout requests and balances by currency"
```

### Task 7: Verify the Alembic migration on a disposable database

**Files:**
- Verify: `backend/alembic/versions/d4e5f6a7b8c9_ledger_amount_currency_invariants.py`

- [ ] **Step 1: Confirm Alembic recognizes the new revision and parent**

Run from `backend/` after creating the migration file in Task 3:

```bash
uv run alembic heads
uv run alembic history -r c2d3e4f5a6b7:head
```

Expected: one head, `d4e5f6a7b8c9`, with `c2d3e4f5a6b7` as its parent.

- [ ] **Step 2: Verify conversion with representative data on an isolated migration database**

From `backend/`, derive the separate database URL without printing its credentials:

```bash
export W05_MIGRATION_DATABASE_URL="$(uv run python -c 'from app.core.config import settings; from sqlalchemy.engine.url import make_url; url = make_url(settings.database_url); print(url.set(database=url.database + "_w05_migration_test").render_as_string(hide_password=False))')"
export W05_MIGRATION_PSQL_URL="$(uv run python -c 'from app.core.config import settings; from sqlalchemy.engine.url import make_url; url = make_url(settings.database_url); print(url.set(drivername="postgresql", database=url.database + "_w05_migration_test").render_as_string(hide_password=False))')"
```

Before creating it, check PostgreSQL and stop if `_w05_migration_test` already exists. If it is absent, obtain explicit user approval before running this project-config-based creation script. It creates only the new database and prints only its name; it never drops or alters the dev database:

```bash
uv run python - <<'PY'
import asyncio

import asyncpg
from sqlalchemy.engine.url import make_url

from app.core.config import settings

base = make_url(settings.database_url)
target_name = f"{base.database}_w05_migration_test"

async def main():
    connection = await asyncpg.connect(
        user=base.username,
        password=base.password,
        host=base.host,
        port=base.port or 5432,
        database="postgres",
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", target_name
        )
        if exists:
            raise RuntimeError("Migration test database exists; stop and inspect it")
        safe_name = target_name.replace('"', '""')
        await connection.execute(f'CREATE DATABASE "{safe_name}"')
    finally:
        await connection.close()
    print(f"Created disposable migration database: {target_name}")

asyncio.run(main())
PY
```

Run the pre-migration schema upgrade from `backend/`:

```bash
DATABASE_URL="$W05_MIGRATION_DATABASE_URL" uv run alembic upgrade c2d3e4f5a6b7
```

Seed this synthetic fixture in the disposable database, in foreign-key order:

```bash
psql "$W05_MIGRATION_PSQL_URL" <<'SQL'
INSERT INTO tenants (id, name, api_key_hash) VALUES
  ('00000000-0000-0000-0000-000000000001', 'w05-tenant', 'w05-api-key');
INSERT INTO affiliate_accounts (id, email, password_hash, name, country, tax_status, tax_entity_type) VALUES
  ('00000000-0000-0000-0000-000000000002', 'w05@example.test', 'unused', 'W05 Affiliate', 'US', 'us_person', 'individual');
INSERT INTO affiliates (id, affiliate_account_id, tenant_id) VALUES
  ('00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001');
INSERT INTO contracts (id, affiliate_id, active) VALUES
  ('00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000003', true);
INSERT INTO terms (id, contract_id, sequence_pattern, commission_percent, minimum_threshold) VALUES
  ('00000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000004', '*', 12.3456789, 1.005);
INSERT INTO events (id, event_id, type, tenant_id, affiliate_id, amount, currency) VALUES
  ('00000000-0000-0000-0000-000000000006', 'w05-usd', 'sale', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000003', 10.005, 'USD'),
  ('00000000-0000-0000-0000-000000000007', 'w05-brl', 'sale', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000003', 20.015, 'BRL'),
  ('00000000-0000-0000-0000-000000000008', 'w05-unsupported', 'sale', '00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000003', 30.005, 'XYZ');
INSERT INTO payment_records (id, tenant_payment_id, tenant_id, amount, currency, status) VALUES
  ('00000000-0000-0000-0000-000000000009', 'w05-payment-usd', '00000000-0000-0000-0000-000000000001', 10.005, 'USD', 'paid');
INSERT INTO commissions (id, event_id, affiliate_id, gross_amount, withholding_amount, net_amount, currency, status) VALUES
  ('00000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000003', 1.005, 0.005, 1.000, 'USD', 'available'),
  ('00000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000003', 2.005, 0.005, 2.000, 'BRL', 'available');
INSERT INTO payouts (id, affiliate_id, tenant_id, requested_amount, approved_amount, withholding_total, paypal_fees, net_paid, currency, status) VALUES
  ('00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', 1.005, 1.005, 0.005, 0.005, 1.000, 'USD', 'pending_approval'),
  ('00000000-0000-0000-0000-000000000013', '00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', 2.005, 2.005, 0.005, 0.005, 2.000, 'BRL', 'pending_approval');
INSERT INTO payout_commissions (id, payout_id, commission_id, amount) VALUES
  ('00000000-0000-0000-0000-000000000014', '00000000-0000-0000-0000-000000000012', '00000000-0000-0000-0000-000000000010', 1.005),
  ('00000000-0000-0000-0000-000000000015', '00000000-0000-0000-0000-000000000013', '00000000-0000-0000-0000-000000000011', 2.005);
SQL
```

Run the migration and inspect representative values:

```bash
DATABASE_URL="$W05_MIGRATION_DATABASE_URL" uv run alembic upgrade head
psql "$W05_MIGRATION_PSQL_URL" -c "SELECT event_id, amount FROM events WHERE event_id LIKE 'w05-%' ORDER BY event_id;"
psql "$W05_MIGRATION_PSQL_URL" -c "SELECT amount, currency FROM payment_records;"
psql "$W05_MIGRATION_PSQL_URL" -c "SELECT currency, gross_amount, withholding_amount, net_amount FROM commissions ORDER BY currency;"
psql "$W05_MIGRATION_PSQL_URL" -c "SELECT currency, requested_amount, approved_amount, withholding_total, paypal_fees, net_paid FROM payouts ORDER BY currency;"
psql "$W05_MIGRATION_PSQL_URL" -c "SELECT amount FROM payout_commissions ORDER BY id;"
psql "$W05_MIGRATION_PSQL_URL" -c "SELECT commission_percent, minimum_threshold FROM terms WHERE id = '00000000-0000-0000-0000-000000000005';"
psql "$W05_MIGRATION_PSQL_URL" -c "SELECT currency, sum(net_amount) FROM commissions GROUP BY currency ORDER BY currency;"
psql "$W05_MIGRATION_PSQL_URL" -c "SELECT count(*) FROM commissions c JOIN events e ON e.id = c.event_id WHERE e.event_id = 'w05-unsupported';"
psql "$W05_MIGRATION_PSQL_URL" -c "SELECT column_name, data_type, numeric_precision, numeric_scale FROM information_schema.columns WHERE table_name = 'commissions' AND column_name = 'gross_amount';"
```

Expected values include USD event amount `10.01`, BRL event amount `20.02`, unsupported event amount `30.01` with zero linked Commissions, `commission_percent = 12.345679`, USD gross commission `1.01`, and BRL gross commission `2.01`. Verify payment-record, payout-commission, and payout amounts plus per-currency sums use the same half-up conversion.

Verify successful downgrade, then exercise the preflight against one deliberately invalid fixture Commission in the disposable database:

```bash
DATABASE_URL="$W05_MIGRATION_DATABASE_URL" uv run alembic downgrade c2d3e4f5a6b7
psql "$W05_MIGRATION_PSQL_URL" -c \
  "INSERT INTO commissions (id, event_id, affiliate_id, gross_amount, withholding_amount, net_amount, currency, status) VALUES ('00000000-0000-0000-0000-000000000016', '00000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000003', 1.00, 0.00, 1.00, 'XYZ', 'pending');"
```

Run the upgrade and verify the expected preflight failure, then inspect the Alembic revision:

```bash
DATABASE_URL="$W05_MIGRATION_DATABASE_URL" uv run alembic upgrade head
psql "$W05_MIGRATION_PSQL_URL" -c "SELECT version_num FROM alembic_version;"
```

Expected: the upgrade exits unsuccessfully with `Cannot migrate commissions with currencies outside USD/EUR/BRL`. Confirm the Alembic version remains `c2d3e4f5a6b7`, delete only the invalid synthetic Commission row, rerun upgrade, and verify success:

```bash
psql "$W05_MIGRATION_PSQL_URL" -c "SELECT version_num FROM alembic_version;"
psql "$W05_MIGRATION_PSQL_URL" -c \
  "DELETE FROM commissions WHERE id = '00000000-0000-0000-0000-000000000016';"
DATABASE_URL="$W05_MIGRATION_DATABASE_URL" uv run alembic upgrade head
psql "$W05_MIGRATION_PSQL_URL" -c "SELECT version_num FROM alembic_version;"
```

Do not delete anything except the named synthetic fixture from this disposable database.

- [ ] **Step 3: Run focused tests and the full suites**

Run from `backend/` with the approved disposable test database:

```bash
uv run pytest tests/test_money.py tests/test_money_models.py tests/test_events.py tests/test_commission.py tests/test_tax.py tests/test_payout.py tests/test_balance.py tests/test_dashboard.py -v
uv run pytest tests/ -v
```

Run from `frontend/`:

```bash
npm run test
npm run build
```

Expected: all tests and the build pass.

- [ ] **Step 4: Update the roadmap and review the final diff**

After every W0.5 acceptance criterion passes, check only the Workstream 0.5 implementation steps and acceptance criteria in `docs/superpowers/plans/2026-09-30-affiliate-service-next-phase-execution-plan.md`. Leave W0.3 and W0.2 unchecked. Run:

```bash
git status --short --branch
git diff --check
git diff
```

- [ ] **Step 5: Commit the completed W0.5 roadmap tracking**

Stage only the W0.5 checkbox/status updates in the roadmap and completed checkboxes in this implementation plan. Do not stage unrelated workstreams or environment files:

```bash
git add docs/superpowers/plans/2026-09-30-affiliate-service-next-phase-execution-plan.md docs/superpowers/plans/2026-09-30-ledger-amount-currency-invariants.md
git commit -m "Mark ledger amount workstream complete"
```

## Acceptance Criteria

- Supported ledger currencies USD, EUR, and BRL use Decimal/Numeric storage and half-up two-decimal calculations; tax rates and jurisdiction logic are unchanged.
- Backend money calculations and SQL aggregates do not use binary floating-point.
- Event provider currency codes are retained; unsupported sale currencies do not create payable commissions and are visibly marked for later replay.
- Replaying a previously unsupported sale after adding its currency creates exactly one Commission.
- Commission, payout, balance, dashboard sales, and merchant liability calculations are currency-scoped.
- Negative reversal rows reduce lifetime earned and appear in a separate positive reversal total, not in pending/available/paid buckets.
- Existing JSON money fields remain numeric; per-currency balance data is additive, and no mixed-currency flat total is returned.
- Migration preflight blocks unsafe existing ledger data; migration upgrade/downgrade passes on a disposable PostgreSQL database.
- Backend tests, frontend tests, and frontend build pass.

## Self-Review

- **Spec coverage:** Decimal/Numeric precision and half-up rounding are covered in Tasks 1–3; provider event retention and replay in Task 4; balance/reversal semantics and currency-grouped dashboards in Task 5; one-currency payout requests and frontend views in Task 6; migration preflight/conversion and disposable-database verification in Task 7.
- **Placeholder scan:** Clean; each implementation and verification step specifies concrete files/actions and expected results.
- **Type/name consistency:** Backend `SUPPORTED_CURRENCY_EXPONENTS`, `normalize_currency_code`, `normalize_provider_amount`, `quantize_ledger_amount`, `build_balances`, and `get_balances` names are consistent across tests and implementation steps. Frontend `CurrencyBalance`, `Balance`, `balances_by_currency`, and `CurrencyBalances({ balance })` names match across types, component, test, and page wiring. API money responses remain numeric while service/model values remain Decimal.
- **Scope boundary:** W-9/W-8 eligibility, tax policy, 14-day availability, manual payout settlement, and the legacy PaymentRecord availability lookup remain unchanged; the latter remains explicitly blocked from production use until W0.2 replaces it.
