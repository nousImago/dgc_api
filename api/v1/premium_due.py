from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, has_permission
from domain.policy.schema import PartyPremiumDue
from services import premium_due as premium_due_service

router = APIRouter()


@router.get(
    "/{party_id}/premium-due",
    response_model=PartyPremiumDue,
    dependencies=[Depends(has_permission("policy.read"))],
)
async def party_premium_due(
    party_id: int, db: AsyncSession = Depends(get_db)
) -> PartyPremiumDue:
    """Premium to collect on the policies where this party is the insured,
    broken down by policy and coverage."""
    return await premium_due_service.premium_due_for_party(db, party_id)
