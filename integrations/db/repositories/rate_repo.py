from collections.abc import Sequence
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.rate.model import RateCell, RateTableVersion


async def resolve_active_version(
    session: AsyncSession, product_id: int, on_date: date
) -> RateTableVersion | None:
    """The active version whose window contains `on_date`. NULL effective_to is
    treated as +infinity. The exclusion constraint guarantees at most one match;
    order_by/limit is belt-and-suspenders."""
    stmt = (
        select(RateTableVersion)
        .where(
            RateTableVersion.product_id == product_id,
            RateTableVersion.status == "active",
            RateTableVersion.effective_from <= on_date,
            or_(
                RateTableVersion.effective_to.is_(None),
                RateTableVersion.effective_to >= on_date,
            ),
        )
        .order_by(RateTableVersion.effective_from.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def list_versions(
    session: AsyncSession, product_id: int
) -> list[RateTableVersion]:
    result = await session.execute(
        select(RateTableVersion)
        .where(RateTableVersion.product_id == product_id)
        .order_by(RateTableVersion.effective_from.desc())
    )
    return list(result.scalars().all())


async def get_version(session: AsyncSession, version_id: int) -> RateTableVersion | None:
    result = await session.execute(
        select(RateTableVersion).where(RateTableVersion.id == version_id)
    )
    return result.scalar_one_or_none()


async def get_cell(
    session: AsyncSession, version_id: int, dim_key: str
) -> RateCell | None:
    stmt = select(RateCell).where(
        RateCell.rate_table_version_id == version_id,
        RateCell.dim_key == dim_key,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def overlapping_active_versions(
    session: AsyncSession,
    product_id: int,
    effective_from: date,
    effective_to: date | None,
) -> list[RateTableVersion]:
    """Active versions for the product whose window overlaps [from, to]. NULL
    effective_to (on either side) means open-ended (+infinity)."""
    upper = effective_to or date.max
    stmt = select(RateTableVersion).where(
        RateTableVersion.product_id == product_id,
        RateTableVersion.status == "active",
        RateTableVersion.effective_from <= upper,
        or_(
            RateTableVersion.effective_to.is_(None),
            RateTableVersion.effective_to >= effective_from,
        ),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def save_version(
    session: AsyncSession, version: RateTableVersion
) -> RateTableVersion:
    session.add(version)
    await session.flush()
    await session.refresh(version)
    return version


async def bulk_add_cells(session: AsyncSession, cells: Sequence[RateCell]) -> None:
    session.add_all(list(cells))
    await session.flush()
