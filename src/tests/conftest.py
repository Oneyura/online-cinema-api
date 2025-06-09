# tests/conftest.py
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from security.token_manager import JWTAuthManager
from src.database.models.accounts import UserGroupEnum, UserGroupModel
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
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture(scope="function")
async def guest_client(client: AsyncClient):
    yield client


@pytest.fixture(scope="function")
async def create_test_user(db_session: AsyncSession):
    """
    Фабрична фікстура для створення тестових користувачів з різними ролями.
    Повертає асинхронну функцію, яку можна викликати в тестах.
    """
    async def _create_test_user_instance(email: str, password: str, role: str, username: str = None):
        # 1. Знайти або створити групу користувачів
        group_name_enum = UserGroupEnum(role)
        group = (await db_session.execute(select(UserGroupModel).filter_by(name=group_name_enum))).scalar_one_or_none()

        if not group:
            group = UserGroupModel(name=group_name_enum)
            db_session.add(group)
            await db_session.commit()
            await db_session.refresh(group)

        # 2. Створити користувача за допомогою фабричного методу UserModel.create
        # Важливо: UserModel.create очікує raw_password, і встановлює _hashed_password через setter
        user = UserModel.create(email=email, raw_password=password, group_id=group.id)

        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # 3. Створити токен доступу, якщо потрібно для аутентифікації в тестах
        # Переконайтеся, що `create_access_token` коректно імпортований
        access_token = JWTAuthManager.create_access_token(data={"sub": user.email, "role": user.group.name.value})

        # Повертаємо інформацію, необхідну для тестування (користувача, його необроблений пароль і токен)
        return {"user": user, "password": password, "access_token": access_token}

    return _create_test_user_instance


@pytest.fixture(scope="function")
async def authenticated_user(db_session: AsyncSession, create_test_user) -> UserModel:
    user_model, _ = await create_test_user("authenticated_user@example.com", "testpass", "user")
    return user_model


@pytest.fixture(scope="function")
async def authenticated_user_client(create_test_user) -> AsyncClient:
    # Створюємо новий екземпляр AsyncClient для цього аутентифікованого клієнта
    # Не передаємо 'client' як залежність, а створюємо його заново
    async with AsyncClient(app=app, base_url="http://test") as ac:
        user_model, plain_password = await create_test_user("authenticated_user@example.com", "testpass", "user")
        login_data = {
            "email": user_model.email,
            "password": plain_password
        }
        response = await ac.post("/auth/login", json=login_data)

        if response.status_code != 200:
            print(
                f"Login failed in authenticated_user_client fixture for {user_model.email}: {response.status_code} - {response.json()}")
            pytest.fail(f"Failed to authenticate user for client: {response.json()}")

        token = response.json()["access_token"]
        ac.headers = {"Authorization": f"Bearer {token}"}
        yield ac
        ac.headers = {}


@pytest.fixture(scope="function")
async def moderator_client(create_test_user) -> AsyncClient:
    # Аналогічно, створюємо новий екземпляр AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as ac:
        moderator_user, plain_password = await create_test_user("moderator@example.com", "password", "moderator")
        login_data = {"email": moderator_user.email, "password": plain_password}
        response = await ac.post("/auth/login", json=login_data)

        if response.status_code != 200:
            print(
                f"Login failed in moderator_client fixture for {moderator_user.email}: {response.status_code} - {response.json()}")
            pytest.fail(f"Failed to authenticate moderator for client: {response.json()}")

        token = response.json()["access_token"]
        ac.headers = {"Authorization": f"Bearer {token}"}
        yield ac
        ac.headers = {}


@pytest.fixture(scope="function")
async def admin_client(create_test_user) -> AsyncClient:
    # І для адміністратора
    async with AsyncClient(app=app, base_url="http://test") as ac:
        admin_user, plain_password = await create_test_user("admin@example.com", "password", "admin")
        login_data = {"email": admin_user.email, "password": plain_password}
        response = await ac.post("/auth/login", json=login_data)

        if response.status_code != 200:
            print(
                f"Login failed in admin_client fixture for {admin_user.email}: {response.status_code} - {response.json()}")
            pytest.fail(f"Failed to authenticate admin for client: {response.json()}")

        token = response.json()["access_token"]
        ac.headers = {"Authorization": f"Bearer {token}"}
        yield ac
        ac.headers = {}
