from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from domain.policy.model import Policy
from domain.policy.schema import PolicyOut
from integrations.db.repositories import policy_repo
from observability.exceptions import NotFoundError

router = APIRouter()


@router.get("", response_model=list[PolicyOut])
async def list_policies(db: AsyncSession = Depends(get_db)) -> list[Policy]:
    return await policy_repo.list_all(db)


@router.get("/{policy_id}", response_model=PolicyOut)
async def get_policy(policy_id: int, db: AsyncSession = Depends(get_db)) -> Policy:
    policy = await policy_repo.get_by_id(db, policy_id)
    if policy is None:
        raise NotFoundError(f"Unknown policy: {policy_id}")
    return policy
