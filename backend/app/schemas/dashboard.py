from datetime import date
from typing import Any

from pydantic import BaseModel


class AffiliateDashboardOut(BaseModel):
    balance: dict[str, float]
    lead_volume: dict[str, int]
    sales_by_sequence: dict[int, dict[str, Any]]
    payouts: list[dict[str, Any]]


class TenantDashboardOut(BaseModel):
    campaign_performance: list[dict[str, Any]]
    affiliates: list[dict[str, Any]]
    commission_liability: float
    payout_queue: list[dict[str, Any]]
