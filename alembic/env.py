"""Alembic environment — async-compatible, auto-discovers all ORM models."""
import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Ensure the repo root is importable regardless of how alembic is invoked.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from domain.base import Base  # noqa: E402

# --- Import every ORM model so its table registers on Base.metadata ---
# When adding a new domain, import it here so autogenerate sees the table.
from domain.user.model import User  # noqa: E402,F401
from domain.role.model import (  # noqa: E402,F401
    Role,
    role_permission,
    user_role,
)
from domain.permission.model import Permission  # noqa: E402,F401

# Insurance core domain
from domain.party.model import Party  # noqa: E402,F401
from domain.product.model import (  # noqa: E402,F401
    Product,
    ProductRatingDimension,
)
from domain.rate.model import (  # noqa: E402,F401
    RateCell,
    RateTableVersion,
)
from domain.policy.model import (  # noqa: E402,F401
    Policy,
    PolicyCoverage,
    PolicyRole,
)
from domain.billing.model import (  # noqa: E402,F401
    PremiumCollectionsSnapshot,
    PremiumForecast,
    PremiumPayment,
    PremiumSchedule,
)

# Alembic Config object
config = context.config

# Apply logging config from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_configuration() -> dict[str, str]:
    """Build the SQLAlchemy config dict, overriding the URL from settings.

    Overrides `sqlalchemy.url` at construction time (rather than via
    `config.set_main_option`) to avoid ConfigParser interpolation errors
    when the password contains `%` characters.
    """
    configuration = config.get_section(config.config_ini_section, {}) or {}
    configuration["sqlalchemy.url"] = settings.database.DATABASE_URL
    return configuration


def run_migrations_offline() -> None:
    """Run migrations in offline mode — emits SQL to stdout, no connection."""
    context.configure(
        url=settings.database.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_as_batch=False,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations online using the async engine."""
    connectable = async_engine_from_config(
        _get_configuration(),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
