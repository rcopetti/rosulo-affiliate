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

