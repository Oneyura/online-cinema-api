from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.config.dependencies import get_current_user, get_current_moderator
from database.models.base import Base
import pytest
import asyncio
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from httpx import AsyncClient

from main import app
from database import get_db
from database.models.accounts import UserRole, UserModel

@pytest.fixture
def client() -> TestClient:
    """
    Create a test client for the FastAPI application.
    """
    return TestClient(app)


@pytest.fixture
def test_app() -> FastAPI:
    """
    Create a test instance of the FastAPI application.
    """
    return app



@pytest.fixture(scope="session")
def event_loop():
    """Фікстура для asyncio event loop, щоб pytest-asyncio міг виконувати асинхронний код."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def async_engine():
    """Створює асинхронний двигун для тестової бази даних (SQLite in-memory)."""
    # Використовуємо SQLite in-memory для швидких тестів
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    yield engine
    await engine.dispose() # Закриваємо з'єднання після тестів

@pytest.fixture(scope="function", autouse=True)
async def setup_db(async_engine):
    """
    Налаштовує та очищує тестову базу даних для кожного тесту.
    Викликає `create_all` на початку та `drop_all` в кінці,
    щоб забезпечити чистий стан для кожного тесту.
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture(scope="function")
async def db_session(async_engine, setup_db) -> AsyncGenerator[AsyncSession, None]:
    """
    Надає асинхронну сесію бази даних для кожного тесту.
    Відкат усіх змін після кожного тесту.
    """
    AsyncTestingSessionLocal = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with AsyncTestingSessionLocal() as session:
        yield session
        # Після кожного тесту відкат змін, щоб база даних була чистою
        await session.rollback()

@pytest.fixture(scope="function")
async def client(db_session: AsyncSession):
    """
    Надає тестовий клієнт FastAPI та мокає залежність `get_db`.
    """
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    # Мокаємо залежності авторизації
    # Для тестів ми імітуватимемо користувачів
    app.dependency_overrides[get_current_user] = lambda: UserModel(id=1, email="testuser@example.com", username="testuser", role=UserRole.user)
    app.dependency_overrides[get_current_moderator] = lambda: UserModel(id=2, email="testmoderator@example.com", username="testmoderator", role=UserRole.moderator)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    # Очищення перекриттів залежностей після тестів
    app.dependency_overrides = {}

# Допоміжна фікстура для створення тестового користувача/модератора в БД, якщо це потрібно для тестів
@pytest.fixture
async def create_test_user(db_session: AsyncSession):
    async def _create_user(email: str, username: str, role: UserRole = UserRole.user):
        user = UserModel(email=email, username=username, role=role)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user
    return _create_user

@pytest.fixture
async def authenticated_client(db_session: AsyncSession, client: AsyncClient):
    """
    Клієнт, який імітує авторизованого користувача.
    """
    test_user = UserModel(id=1, email="authuser@example.com", username="authuser", role=UserRole.user)
    db_session.add(test_user)
    await db_session.commit()
    await db_session.refresh(test_user)

    app.dependency_overrides[get_current_user] = lambda: test_user
    yield client
    app.dependency_overrides = {} # Очищення

@pytest.fixture
async def moderator_client(db_session: AsyncSession, client: AsyncClient):
    """
    Клієнт, який імітує авторизованого модератора.
    """
    test_moderator = UserModel(id=2, email="mod@example.com", username="moderator", role=UserRole.moderator)
    db_session.add(test_moderator)
    await db_session.commit()
    await db_session.refresh(test_moderator)

    app.dependency_overrides[get_current_moderator] = lambda: test_moderator
    yield client
    app.dependency_overrides = {} # Очищення
