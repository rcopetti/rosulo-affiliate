from fastapi import APIRouter

from app.api.v1.admin import affiliates as admin_affiliates
from app.api.v1.admin import contracts as admin_contracts
from app.api.v1.admin import dashboard as admin_dashboard
from app.api.v1.admin import events as admin_events
from app.api.v1.admin import integrations as admin_integrations
from app.api.v1.admin import payouts as admin_payouts
from app.api.v1.affiliate import balance as affiliate_balance
from app.api.v1.affiliate import campaigns as affiliate_campaigns
from app.api.v1.affiliate import dashboard as affiliate_dashboard
from app.api.v1.affiliate import merchants as affiliate_merchants
from app.api.v1.affiliate import payouts as affiliate_payouts
from app.api.v1.affiliate import profile as affiliate_profile
from app.api.v1.auth import affiliate as auth_affiliate
from app.api.v1.auth import password_reset as auth_password_reset
from app.api.v1.auth import tenant as auth_tenant
from app.api.v1.public import events as public_events
from app.api.v1.public import webhooks as public_webhooks

router = APIRouter()

router.include_router(auth_affiliate.router, prefix="/auth", tags=["auth"])
router.include_router(auth_tenant.router, prefix="/auth", tags=["auth"])
router.include_router(auth_password_reset.router, prefix="/auth/password-reset", tags=["auth"])
router.include_router(admin_contracts.router, prefix="/admin/affiliates", tags=["admin-contracts"])
router.include_router(admin_affiliates.router, prefix="/admin/affiliates", tags=["admin-affiliates"])
router.include_router(admin_payouts.router, prefix="/admin/payouts", tags=["admin-payouts"])
router.include_router(admin_events.router, prefix="/admin/events", tags=["admin-events"])
router.include_router(admin_integrations.router, prefix="/admin/integration", tags=["admin-integration"])
router.include_router(admin_dashboard.router, prefix="/admin/dashboard", tags=["admin-dashboard"])
router.include_router(affiliate_merchants.router, prefix="/affiliate/merchants", tags=["affiliate-merchants"])
router.include_router(affiliate_profile.router, prefix="/affiliate", tags=["affiliate-profile"])
router.include_router(affiliate_campaigns.router, prefix="/affiliate/campaigns", tags=["affiliate-campaigns"])
router.include_router(affiliate_balance.router, prefix="/affiliate", tags=["affiliate-balance"])
router.include_router(affiliate_payouts.router, prefix="/affiliate", tags=["affiliate-payouts"])
router.include_router(affiliate_dashboard.router, prefix="/affiliate/dashboard", tags=["affiliate-dashboard"])
router.include_router(public_events.router, prefix="/events", tags=["events"])
router.include_router(public_webhooks.router, prefix="/webhooks", tags=["webhooks"])
