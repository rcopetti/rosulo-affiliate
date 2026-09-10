from app.db.models import AffiliateAccount


def compute_withholding_rate(account: AffiliateAccount) -> float:
    if account.tax_status == "us_person":
        return 0.24 if account.backup_withholding_required else 0.0
    return 0.30


def apply_tax(account: AffiliateAccount, gross_amount: float) -> tuple[float, float, float]:
    rate = compute_withholding_rate(account)
    withholding = round(gross_amount * rate, 2)
    net = round(gross_amount - withholding, 2)
    return gross_amount, withholding, net
