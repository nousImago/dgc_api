from sqlalchemy.ext.asyncio import AsyncSession

from integrations.db.session import async_session_factory


class UnitOfWork:
    """Explicit transaction boundary for multi-repository operations.

    Use when a single business operation touches multiple aggregates and must
    commit atomically (e.g., issuing a policy creates the policy contract and
    its base + rider coverages in one transaction).

        async with UnitOfWork() as uow:
            policy = await policy_repo.save_policy(uow.session, policy)
            for coverage in coverages:
                await policy_repo.save_coverage(uow.session, coverage)
        # commits on successful exit, rolls back on exception
    """

    session: AsyncSession

    async def __aenter__(self) -> "UnitOfWork":
        self.session = async_session_factory()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is not None:
                await self.session.rollback()
            else:
                await self.session.commit()
        finally:
            await self.session.close()
