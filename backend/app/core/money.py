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
