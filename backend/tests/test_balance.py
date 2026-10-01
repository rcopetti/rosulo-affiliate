from decimal import Decimal

from app.services.balance import add_legacy_balance_fields, build_balances


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
    assert add_legacy_balance_fields([by_currency["USD"]])["debt"] == Decimal("3.00")
    assert by_currency["EUR"]["earned"] == Decimal("7.00")
    assert by_currency["EUR"]["available"] == Decimal("7.00")
