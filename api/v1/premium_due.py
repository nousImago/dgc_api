from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, has_permission
from domain.policy.schema import CustomerPremiumDue
from services import premium_due as premium_due_service

router = APIRouter()


@router.get(
    "/{customer_id}/premium-due",
    response_model=CustomerPremiumDue,
    dependencies=[Depends(has_permission("policy.read"))],
)
async def customer_premium_due(
    customer_id: int, db: AsyncSession = Depends(get_db)
) -> CustomerPremiumDue:
    """Demo centrepiece: the premium to collect for a customer, broken down by
    policy and coverage (base + riders)."""
    return await premium_due_service.premium_due_for_customer(db, customer_id)
