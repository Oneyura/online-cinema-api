from typing import AsyncGenerator, cast

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine
)
from sqlalchemy.orm import sessionmaker

from src.config.settings import BaseAppSettings


async def get_postgres_async_engine(settings: BaseAppSettings) -> AsyncEngine:
    """Create async PostgreSQL engine."""
    return create_async_engine(
        settings.POSTGRES_DATABASE_URL,  # type: ignore
        echo=settings.DEBUG,  # type: ignore
        future=True,
    )


def get_postgres_async_session_maker(
    engine: AsyncEngine,
) -> sessionmaker:
    """Create async session maker for PostgreSQL."""
    session_factory = sessionmaker(  # type: ignore
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return cast(sessionmaker, session_factory)


async def get_postgres_async_session(
    session_maker: sessionmaker,
) -> AsyncGenerator[AsyncSession, None]:
    """Get async session for PostgreSQL."""
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
