from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.customer.model import Customer


async def get_by_id(session: AsyncSession, customer_id: int) -> Customer | None:
    """Load a customer with their full policy → coverage → product/version tree
    (all relationships are selectin, so the rollup is eagerly available)."""
    result = await session.execute(select(Customer).where(Customer.id == customer_id))
    return result.scalar_one_or_none()


async def get_by_external_ref(session: AsyncSession, external_ref: str) -> Customer | None:
    result = await session.execute(
        select(Customer).where(Customer.external_ref == external_ref)
    )
    return result.scalar_one_or_none()


async def list_all(session: AsyncSession) -> list[Customer]:
    result = await session.execute(select(Customer).order_by(Customer.full_name))
    return list(result.scalars().all())


async def save(session: AsyncSession, customer: Customer) -> Customer:
    session.add(customer)
    await session.flush()
    await session.refresh(customer)
    return customer
