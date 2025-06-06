from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config.dependencies import get_settings


settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.POSTGRES_DATABASE_URL,  # type: ignore
    echo=settings.DEBUG,  # type: ignore
    future=True,
)

# Create async session factory
AsyncSessionLocal = sessionmaker[AsyncSession](  # type: ignore
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# Dependency for FastAPI
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session."""
    async with AsyncSessionLocal() as session:
        yield session
