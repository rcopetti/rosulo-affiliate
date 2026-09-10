import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class TermBase(BaseModel):
    payment_sequence: int | None = None
    sequence_pattern: str = "*"
    commission_percent: float = Field(..., ge=0, le=100)
    minimum_threshold: float | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class TermCreate(TermBase):
    pass


class TermUpdate(BaseModel):
    payment_sequence: int | None = None
    sequence_pattern: str | None = None
    commission_percent: float | None = Field(None, ge=0, le=100)
    minimum_threshold: float | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class TermOut(TermBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    contract_id: uuid.UUID


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    affiliate_id: uuid.UUID
    active: bool
    terms: list[TermOut]


class ContractUpdate(BaseModel):
    active: bool | None = None
