from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from config import settings

# Import all domain models so SQLAlchemy's mapper can resolve every
# relationship and association table before the first query runs. Add each
# new domain's model module here as you build features.
import domain.permission.model  # noqa: F401
import domain.role.model  # noqa: F401
import domain.user.model  # noqa: F401

engine: AsyncEngine = create_async_engine(
    settings.database.DATABASE_URL,
    pool_size=settings.database.DB_POOL_SIZE,
    max_overflow=settings.database.DB_MAX_OVERFLOW,
    pool_recycle=settings.database.DB_POOL_RECYCLE,
    pool_pre_ping=True,
    echo=settings.database.DB_ECHO,
    future=True,
)
