from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from domain.role.model import Role
from domain.user.model import User


async def get_by_ids(session: AsyncSession, ids: list[int]) -> dict[int, User]:
    if not ids:
        return {}
    result = await session.execute(select(User).where(User.id.in_(ids)))
    return {u.id: u for u in result.scalars().all()}


async def get_by_id(session: AsyncSession, user_id: int) -> User | None:
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    stmt = (
        select(User)
        .where(User.username == username)
        .options(selectinload(User.roles).selectinload(Role.permissions))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def search(
    session: AsyncSession,
    q: str,
    *,
    role: str | None = None,
    include_inactive: bool = False,
    limit: int = 20,
) -> list[User]:
    stmt = select(User).options(selectinload(User.roles))
    if not include_inactive:
        stmt = stmt.where(User.active == True)  # noqa: E712
    if q:
        pattern = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.full_name).like(pattern),
                func.lower(User.username).like(pattern),
            )
        )
    if role:
        stmt = stmt.join(User.roles).where(func.lower(Role.code) == role.lower())
    stmt = stmt.order_by(User.full_name).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().unique().all())


async def save(session: AsyncSession, user: User) -> User:
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def set_roles(session: AsyncSession, user: User, role_ids: list[int]) -> None:
    roles = list(
        (await session.execute(select(Role).where(Role.id.in_(role_ids)))).scalars().all()
    )
    user.roles = roles


async def list_roles(session: AsyncSession) -> list[Role]:
    result = await session.execute(
        select(Role).where(Role.active == True).order_by(Role.name)  # noqa: E712
    )
    return list(result.scalars().all())
