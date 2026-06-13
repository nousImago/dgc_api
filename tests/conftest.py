import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import domain.customer.model  # noqa: F401
import domain.permission.model  # noqa: F401
import domain.policy.model  # noqa: F401
import domain.product.model  # noqa: F401
import domain.rate.model  # noqa: F401
import domain.role.model  # noqa: F401

# Import every model module so all tables register on Base.metadata.
import domain.user.model  # noqa: F401
from domain.base import Base

TEST_DB_URL = "postgresql+asyncpg://dgc:password@localhost:5432/dgc_test"


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """Function-scoped engine + fresh schema, all created in the test's own
    event loop (asyncpg connections are loop-bound, so a shared session-scoped
    engine breaks across pytest-asyncio's per-test loops). NullPool avoids any
    connection reuse across loops."""
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
        await s.rollback()

    await engine.dispose()
