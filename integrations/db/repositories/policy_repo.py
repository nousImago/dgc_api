from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from domain.party.model import Party
from domain.policy.model import Policy, PolicyCoverage, PolicyRole
from domain.product.model import Product

# Policy.coverages, Policy.roles, PolicyRole.party, PolicyCoverage.product/version
# are all lazy="selectin", so any Policy query eager-loads the full tree.


async def get_by_id(session: AsyncSession, policy_id: int) -> Policy | None:
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


async def list_for_party(
    session: AsyncSession, party_id: int, role: str | None = None
) -> list[Policy]:
    """Policies on which the party holds a role (any role, or a specific one)."""
    cond = PolicyRole.party_id == party_id
    if role is not None:
        cond = and_(cond, PolicyRole.role == role)
    result = await session.execute(
        select(Policy).where(Policy.roles.any(cond)).order_by(Policy.policy_number)
    )
    return list(result.scalars().all())


async def list_filtered(
    session: AsyncSession,
    *,
    product_code: str | None = None,
    q: str | None = None,
) -> list[Policy]:
    """All policies matching the register filters. Ordered by policy number.

    NOTE: the register sums/sorts premium in Python because premium is computed
    live by the rating engine. At production scale, materialise the premium on
    the policy (or a billing/invoice row) so pagination, sort, and SUM push down
    into indexed SQL instead of an O(all-policies) live pass.
    """
    stmt = select(Policy)
    if product_code:
        stmt = stmt.where(
            Policy.coverages.any(PolicyCoverage.product.has(Product.code == product_code))
        )
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Policy.policy_number.ilike(pattern),
                # search the INSURED party's name
                Policy.roles.any(
                    and_(
                        PolicyRole.role == "insured",
                        PolicyRole.party.has(Party.full_name.ilike(pattern)),
                    )
                ),
            )
        )
    stmt = stmt.order_by(Policy.policy_number)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def next_policy_number(session: AsyncSession) -> str:
    """Concurrency-safe policy number from the Postgres sequence."""
    result = await session.execute(text("SELECT nextval('policy_number_seq')"))
    return f"P-{int(result.scalar_one()):04d}"


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


async def save_role(session: AsyncSession, role: PolicyRole) -> PolicyRole:
    session.add(role)
    await session.flush()
    await session.refresh(role)
    return role
