from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.policy.model import Policy, PolicyCoverage


async def get_by_id(session: AsyncSession, policy_id: int) -> Policy | None:
    """Load a policy with its coverages → product/version (selectin)."""
    result = await session.execute(select(Policy).where(Policy.id == policy_id))
    return result.scalar_one_or_none()


async def get_by_number(session: AsyncSession, policy_number: str) -> Policy | None:
    result = await session.execute(
        select(Policy).where(Policy.policy_number == policy_number)
    )
    return result.scalar_one_or_none()


async def list_all(session: AsyncSession) -> list[Policy]:
    result = await session.execute(select(Policy).order_by(Policy.policy_number))
    return list(result.scalars().all())


async def list_for_customer(session: AsyncSession, customer_id: int) -> list[Policy]:
    result = await session.execute(
        select(Policy)
        .where(Policy.customer_id == customer_id)
        .order_by(Policy.policy_number)
    )
    return list(result.scalars().all())


async def save_policy(session: AsyncSession, policy: Policy) -> Policy:
    session.add(policy)
    await session.flush()
    await session.refresh(policy)
    return policy


async def save_coverage(
    session: AsyncSession, coverage: PolicyCoverage
) -> PolicyCoverage:
    session.add(coverage)
    await session.flush()
    await session.refresh(coverage)
    return coverage
