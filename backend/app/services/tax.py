from decimal import Decimal

from app.core.money import normalize_provider_amount
from app.db.models import AffiliateAccount


def compute_withholding_rate(account: AffiliateAccount) -> Decimal:
    if account.tax_status == "us_person":
        return Decimal("0.24") if account.backup_withholding_required else Decimal("0.00")
    return Decimal("0.30")


def apply_tax(
    account: AffiliateAccount, gross_amount: Decimal
) -> tuple[Decimal, Decimal, Decimal]:
    rate = compute_withholding_rate(account)
    withholding = normalize_provider_amount(gross_amount * rate)
    net = normalize_provider_amount(gross_amount - withholding)
    return gross_amount, withholding, net
