from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DueItem(BaseModel):
    """One outstanding obligation — the unit of the Collection Management worklist."""

    model_config = ConfigDict(from_attributes=True)

    schedule_id: int
    policy_id: int
    policy_number: str
    payer_party_id: int | None
    payer_name: str
    product_summary: str
    due_date: date
    base_amount: Decimal
    rider_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal
    outstanding: Decimal
    status: str
    days_overdue: int


class DueItemsPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[DueItem]


class CollectionsSummary(BaseModel):
    total_outstanding: Decimal = Decimal("0.00")
    overdue_count: int = 0
    overdue_amount: Decimal = Decimal("0.00")
    due_soon_amount: Decimal = Decimal("0.00")
    collected_this_month: Decimal = Decimal("0.00")


class PaymentRecord(BaseModel):
    payment_id: int
    schedule_id: int
    policy_id: int
    policy_number: str
    payer_name: str
    paid_date: date
    amount: Decimal
    method: str
    reference_no: str | None
    status: str
    recorded_by: str | None


class PaymentsPage(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PaymentRecord]


class RecordPaymentInput(BaseModel):
    schedule_id: int
    paid_date: date
    amount: Decimal = Field(gt=0)
    method: str = "transfer"
    reference_no: str | None = None
    notes: str | None = None
