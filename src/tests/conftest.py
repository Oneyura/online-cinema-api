import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import UserModel
from src.database.models.base import Base
from src.main import app
from src.config.dependencies import get_db

@pytest.fixture(scope="module")
async def async_engine():
    engine = create_async_engine("sqlite+aiosqlite:///./test.db", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.fixture(scope="function")
async def db_session(async_engine):
    AsyncSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with AsyncSessionLocal() as session:
        yield session

@pytest.fixture(scope="function")
async def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def guest_client(client: AsyncClient):
    yield client

@pytest.fixture(scope="function")
async def authenticated_user_client(client: AsyncClient, create_test_user):
    user_id, token = await create_test_user("testuser", "password", "user")
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client
    client.headers = {} # Очистити заголовки після тесту

@pytest.fixture(scope="function")
async def moderator_client(client: AsyncClient, create_test_user):
    user_id, token = await create_test_user("moderator", "password", "moderator")
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client
    client.headers = {} # Очистити заголовки після тесту

@pytest.fixture(scope="function")
async def admin_client(client: AsyncClient, create_test_user):
    user_id, token = await create_test_user("admin", "password", "admin")
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client
    client.headers = {}

@pytest.fixture(scope="function")
async def create_test_user(db_session: AsyncSession):
    async def _create_test_user(username, password, role):

        user = UserModel(
            username=username,
            password=password,
            role=role
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        dummy_token = f"dummy_token_for_{username}"
        return user.id, dummy_token
    return _create_test_user
