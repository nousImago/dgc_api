from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, has_permission
from domain.party.model import Party
from domain.party.schema import PartyCreate, PartyOut
from domain.policy.model import Policy
from domain.policy.schema import PolicyOut
from integrations.db.repositories import party_repo, policy_repo
from observability.exceptions import NotFoundError
from services.issuance import new_external_ref

router = APIRouter()


@router.get("", response_model=list[PartyOut])
async def list_parties(db: AsyncSession = Depends(get_db)) -> list[Party]:
    return await party_repo.list_all(db)


@router.get("/{party_id}", response_model=PartyOut)
async def get_party(party_id: int, db: AsyncSession = Depends(get_db)) -> Party:
    party = await party_repo.get_by_id(db, party_id)
    if party is None:
        raise NotFoundError(f"Unknown party: {party_id}")
    return party


@router.post(
    "",
    response_model=PartyOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_permission("customer.manage"))],
)
async def create_party(
    payload: PartyCreate, db: AsyncSession = Depends(get_db)
) -> Party:
    party = Party(
        external_ref=payload.external_ref or new_external_ref(),
        full_name=payload.full_name,
        sex=payload.sex,
        date_of_birth=payload.date_of_birth,
        party_type=payload.party_type,
    )
    return await party_repo.save(db, party)


@router.get("/{party_id}/policies", response_model=list[PolicyOut])
async def party_policies(
    party_id: int, db: AsyncSession = Depends(get_db)
) -> list[Policy]:
    """Policies the party holds any role on (for the Party hub)."""
    return await policy_repo.list_for_party(db, party_id)
