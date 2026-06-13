from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.customer.model import Customer
from domain.policy.model import Policy, PolicyCoverage
from domain.product.model import Product


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


async def list_filtered(
    session: AsyncSession,
    *,
    product_code: str | None = None,
    q: str | None = None,
) -> list[Policy]:
    """All policies matching the register filters, with customer + coverages
    eagerly loaded for live premium computation. Ordered by policy number.

    NOTE: the register sums/sorts premium in Python because premium is computed
    live by the rating engine. At production scale, materialise the premium on
    the policy (or a billing/invoice row) so pagination, sort, and SUM push down
    into indexed SQL instead of an O(all-policies) live pass.
    """
    stmt = select(Policy).options(selectinload(Policy.customer))
    if product_code:
        stmt = stmt.where(
            Policy.coverages.any(PolicyCoverage.product.has(Product.code == product_code))
        )
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Policy.policy_number.ilike(pattern),
                Policy.customer.has(Customer.full_name.ilike(pattern)),
            )
        )
    stmt = stmt.order_by(Policy.policy_number)
    result = await session.execute(stmt)
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
