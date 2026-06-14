from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, has_permission
from domain.policy.model import Policy
from domain.policy.schema import PolicyIssueRequest, PolicyOut
from integrations.db.repositories import policy_repo
from observability.exceptions import NotFoundError
from services import issuance

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


@router.post(
    "",
    response_model=PolicyOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(has_permission("policy.manage"))],
)
async def issue_policy(
    payload: PolicyIssueRequest, db: AsyncSession = Depends(get_db)
) -> Policy:
    """New Business → Issue: create a policy with coverages + party roles."""
    return await issuance.issue_policy(db, payload)
