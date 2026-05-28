from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings


def _async_url(url: str) -> str:
    """Ensure the URL uses the asyncpg driver."""
    return (
        url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
           .replace("postgresql://", "postgresql+asyncpg://", 1)
    )


engine = create_async_engine(_async_url(settings.database_url), echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    """Create all tables without migrations. Use Alembic in production."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
