import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# Load our app config and all models so autogenerate can detect the full schema
from mednotebook_backend.config import settings
from mednotebook_backend.database import Base
import mednotebook_backend.models  # noqa: F401 — registers all models with Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _async_url(url: str) -> str:
    return (
        url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
           .replace("postgresql://", "postgresql+asyncpg://", 1)
    )


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        context.run_migrations()


def run_migrations_offline() -> None:
    """Generate SQL to stdout without a live connection."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against a live database via asyncpg."""
    connectable = create_async_engine(
        _async_url(settings.database_url),
        poolclass=pool.NullPool,
    )
    # Use begin() so the transaction is committed on clean exit
    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
