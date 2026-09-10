from datetime import date
from typing import Any

from pydantic import BaseModel


class BalanceOut(BaseModel):
    earned: float
    pending: float
    available: float
    paid: float
    tax_retained: float
    debt: float
    currency: str


class LeadVolumePoint(BaseModel):
    bucket: str
    count: int


class SalesBySequencePoint(BaseModel):
    sequence: int
    count: int
    amount: float


class AffiliateDashboardOut(BaseModel):
    balance: BalanceOut
    lead_volume: list[LeadVolumePoint]
    sales_by_sequence: list[SalesBySequencePoint]
    payouts: list[dict[str, Any]]


class CampaignPerformanceRow(BaseModel):
    campaign_id: str
    name: str
    clicks: int
    leads: int
    sales: int


class CommissionLiabilityRow(BaseModel):
    period: str
    gross: float
    tax_retained: float


class TenantDashboardOut(BaseModel):
    campaign_performance: list[CampaignPerformanceRow]
    affiliates: list[dict[str, Any]]
    commission_liability: list[CommissionLiabilityRow]
    payout_queue: list[dict[str, Any]]
