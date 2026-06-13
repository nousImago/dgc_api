from sqlalchemy.ext.asyncio import AsyncSession

from integrations.db.session import async_session_factory


class UnitOfWork:
    """Explicit transaction boundary for multi-repository operations.

    Use when a single business operation touches multiple aggregates and must
    commit atomically (e.g., approving finance updates a job, creates invoice,
    and credits coin history in one transaction).

        async with UnitOfWork() as uow:
            job = await job_auto_repo.get(uow.session, job_number)
            job.finance_status = "approved"
            await job_auto_repo.save(uow.session, job)
            await invoice_repo.create(uow.session, invoice)
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
