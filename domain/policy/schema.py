from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class CoverageCreate(BaseModel):
    product_code: str
    sum_assured: Decimal


class PolicyCreate(BaseModel):
    policy_number: str = Field(min_length=1, max_length=32)
    customer_id: int
    effective_date: date
    coverages: list[CoverageCreate] = Field(default_factory=list)


class CoverageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    sum_assured: Decimal
    status: str
    rate_table_version_id: int | None = None


class PolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    policy_number: str
    customer_id: int
    effective_date: date
    status: str
    coverages: list[CoverageOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


# --- Premium-due rollup (customer → policies → coverages) ---


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


class CustomerPremiumDue(BaseModel):
    customer_id: int
    full_name: str
    total_due: Decimal
    policies: list[PremiumDuePolicy] = Field(default_factory=list)
