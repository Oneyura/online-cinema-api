# tests/conftest.py
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
    # Цей client не є аутентифікованим (гість)
    app.dependency_overrides[get_db] = lambda: db_session
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
async def guest_client(client: AsyncClient):
    # Просто повертаємо неаутентифікований client
    yield client

# МОДИФІКОВАНО: create_test_user
@pytest.fixture(scope="function")
async def create_test_user(db_session: AsyncSession):
    """
    Колекційна фікстура для створення тестового користувача.
    Повертає: (UserModel, str) - (об'єкт користувача, звичайний (plain) пароль)
    """
    async def _create_test_user(email: str, password: str, role: str, username: str = None):
        if username is None:
            username = email.split('@')[0] # За замовчуванням username з email

        # ВАЖЛИВО: Якщо поле 'password' у вашій моделі UserModel зберігає ХЕШОВАНИЙ пароль,
        # вам *обов'язково* потрібно хешувати 'password' тут перед створенням екземпляра UserModel.
        # Наприклад:
        # from src.auth.security import hash_password # Імпортуйте ваш хешер
        # hashed_password = hash_password(password)
        # user = UserModel(email=email, password=hashed_password, role=role, username=username)

        # Для простоти тестування, припускаємо, щоUserModel може прийняти звичайний пароль,
        # або що ваш ендпоінт /auth/login сам хешує вхідний пароль.
        user = UserModel(
            email=email,
            password=password, # Зберігаємо звичайний пароль для цього прикладу
            role=role,
            username=username
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)

        # Повертаємо об'єкт користувача та його звичайний пароль
        return user, password
    return _create_test_user

# ДОДАНО: authenticated_user
@pytest.fixture(scope="function")
async def authenticated_user(db_session: AsyncSession, create_test_user) -> UserModel:
    """
    Фікстура, яка створює та повертає екземпляр UserModel для аутентифікованого користувача.
    """
    # Створюємо користувача за допомогою фікстури create_test_user
    user_model, _ = await create_test_user("authenticated_user@example.com", "testpass", "user")
    return user_model

# МОДИФІКОВАНО: authenticated_user_client
@pytest.fixture(scope="function")
async def authenticated_user_client(client: AsyncClient, authenticated_user: UserModel) -> AsyncClient:
    """
    Фікстура, яка надає AsyncClient, аутентифікований як 'authenticated_user'.
    """
    login_data = {
        "email": authenticated_user.email,
        "password": "testpass" # Це має бути звичайний пароль, який використовувався при створенні користувача
    }
    response = await client.post("/auth/login", json=login_data)

    if response.status_code != 200:
        print(f"Login failed in authenticated_user_client fixture for {authenticated_user.email}: {response.status_code} - {response.json()}")
        pytest.fail(f"Failed to authenticate user for client: {response.json()}")

    token = response.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client
    client.headers = {} # Очистити заголовки після тесту

# МОДИФІКОВАНО: moderator_client
@pytest.fixture(scope="function")
async def moderator_client(client: AsyncClient, create_test_user):
    moderator_user, password = await create_test_user("moderator@example.com", "password", "moderator")
    login_data = {"email": moderator_user.email, "password": password}
    response = await client.post("/auth/login", json=login_data)
    token = response.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client
    client.headers = {} # Очистити заголовки після тесту

# МОДИФІКОВАНО: admin_client
@pytest.fixture(scope="function")
async def admin_client(client: AsyncClient, create_test_user):
    admin_user, password = await create_test_user("admin@example.com", "password", "admin")
    login_data = {"email": admin_user.email, "password": password}
    response = await client.post("/auth/login", json=login_data)
    token = response.json()["access_token"]
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client
    client.headers = {}