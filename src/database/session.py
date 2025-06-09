from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config.settings import Settings

settings = Settings()

# Create async engine
engine = create_async_engine(
    settings.database_url,  # type: ignore
    echo=settings.DB_ECHO_LOG,  # type: ignore
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
