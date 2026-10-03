from datetime import date
from typing import Any

from pydantic import BaseModel


class CurrencyBalanceOut(BaseModel):
    currency: str
    earned: float
    pending: float
    available: float
    reserved: float
    paid: float
    tax_retained: float
    reversal_total: float


class BalanceOut(BaseModel):
    balances_by_currency: list[CurrencyBalanceOut]
    earned: float | None
    pending: float | None
    available: float | None
    reserved: float | None
    paid: float | None
    reversed: float | None
    tax_retained: float | None
    reversal_total: float | None
    debt: float | None
    currency: str | None


class LeadVolumePoint(BaseModel):
    bucket: str
    count: int


class SalesBySequencePoint(BaseModel):
    sequence: int
    count: int
    amount: float
    currency: str


class AffiliateDashboardOut(BaseModel):
    balance: BalanceOut
    lead_volume: list[LeadVolumePoint]
    sales_volume: list[LeadVolumePoint]
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
    currency: str


class TenantDashboardOut(BaseModel):
    campaign_performance: list[CampaignPerformanceRow]
    affiliates: list[dict[str, Any]]
    commission_liability: list[CommissionLiabilityRow]
    payout_queue: list[dict[str, Any]]
