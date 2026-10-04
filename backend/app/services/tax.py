from decimal import Decimal

from app.core.money import normalize_provider_amount
from app.db.models import AffiliateAccount


NO_WITHHOLDING_COUNTRIES = {"BR", "BRAZIL"}


def compute_withholding_rate(account: AffiliateAccount) -> Decimal:
    """US payees are never withheld (W-9 only); Brazilian payees, individual
    or business, are also exempt. Other foreign payees without a W-8 treaty
    claim are withheld at the statutory 30%."""
    if account.tax_status == "us_person":
        return Decimal("0.00")
    if (account.country or "").strip().upper() in NO_WITHHOLDING_COUNTRIES:
        return Decimal("0.00")
    return Decimal("0.30")


def apply_tax(
    account: AffiliateAccount, gross_amount: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    rate = compute_withholding_rate(account)
    withholding = normalize_provider_amount(gross_amount * rate)
    net = normalize_provider_amount(gross_amount - withholding)
    return gross_amount, withholding, net
