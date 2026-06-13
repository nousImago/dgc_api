from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RateTableVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    source_ref: str
    unit_basis: Decimal
    effective_from: date
    effective_to: date | None = None
    status: str
    cell_count: int
    created_at: datetime


class QuoteRequest(BaseModel):
    product_code: str
    effective_date: date
    dimensions: dict[str, Any] = Field(default_factory=dict)
    sum_assured: Decimal


class QuoteResult(BaseModel):
    """What the headless rating engine returns: the looked-up rate plus the
    premium scaled to the requested sum assured."""

    product_code: str
    rate_table_version_id: int
    source_ref: str
    dimensions: dict[str, Any]
    gross_before_discount: Decimal
    unit_basis: Decimal
    sum_assured: Decimal
    premium: Decimal
