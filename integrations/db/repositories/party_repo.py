from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.party.model import Party


async def get_by_id(session: AsyncSession, party_id: int) -> Party | None:
    result = await session.execute(select(Party).where(Party.id == party_id))
    return result.scalar_one_or_none()


async def get_by_external_ref(session: AsyncSession, external_ref: str) -> Party | None:
    result = await session.execute(
        select(Party).where(Party.external_ref == external_ref)
    )
    return result.scalar_one_or_none()


async def list_all(session: AsyncSession) -> list[Party]:
    result = await session.execute(select(Party).order_by(Party.full_name))
    return list(result.scalars().all())


async def save(session: AsyncSession, party: Party) -> Party:
    session.add(party)
    await session.flush()
    await session.refresh(party)
    return party
