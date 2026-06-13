from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from domain.party.schema import PartyRef


class CoverageInput(BaseModel):
    product_code: str
    sum_assured: Decimal


class PolicyIssueRequest(BaseModel):
    """New Business → Issue. Each party is inline create-or-pick (see PartyRef)."""

    effective_date: date
    owner: PartyRef
    insured: PartyRef
    beneficiary: PartyRef | None = None
    coverages: list[CoverageInput] = Field(min_length=1)


class CoverageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    sum_assured: Decimal
    status: str
    rate_table_version_id: int | None = None


class PolicyRoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    party_id: int
    role: str
    party_name: str
    allocation_pct: Decimal | None = None


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    policy_number: str
    effective_date: date
    status: str
    coverages: list[CoverageOut] = Field(default_factory=list)
    roles: list[PolicyRoleOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# --- Premium-due rollup (party → policies → coverages) ---


class PremiumDueCoverageLine(BaseModel):
    product_code: str
    kind: str
    age: int | None = None
    sex: str
    sum_assured: Decimal
    gross_before_discount: Decimal | None = None
    premium: Decimal | None = None
    error: str | None = None


class PremiumDuePolicy(BaseModel):
    policy_number: str
    effective_date: date
    premium: Decimal
    coverages: list[PremiumDueCoverageLine] = Field(default_factory=list)


class PartyPremiumDue(BaseModel):
    party_id: int
    full_name: str
    total_due: Decimal
    policies: list[PremiumDuePolicy] = Field(default_factory=list)


# --- Application quote (pre-issue; persists nothing) ---


class ApplicationQuoteRequest(BaseModel):
    effective_date: date
    insured: PartyRef
    coverages: list[CoverageInput] = Field(min_length=1)


class ApplicationQuoteResult(BaseModel):
    total: Decimal
    coverages: list[PremiumDueCoverageLine] = Field(default_factory=list)


# --- Premium register (portfolio worklist: one row per policy) ---


class PremiumRegisterItem(BaseModel):
    policy_id: int
    policy_number: str
    party_id: int
    insured_name: str
    effective_date: date
    products: str
    coverage_count: int
    premium_due: Decimal
    has_error: bool
    coverages: list[PremiumDueCoverageLine] = Field(default_factory=list)


class PremiumRegisterPage(BaseModel):
    total_policies: int
    total_outstanding: Decimal
    page: int
    page_size: int
    items: list[PremiumRegisterItem] = Field(default_factory=list)
