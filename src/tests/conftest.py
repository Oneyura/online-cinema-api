import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import sessionmaker

from src.database.models.accounts import UserGroupEnum
from src.security.interfaces import JWTAuthManagerInterface
from src.database.session import engine, AsyncSessionLocal
from src.database.models import UserModel
from src.database.models.base import Base
from src.main import app
from src.config.dependencies import get_db

# --- ПІДХІД З БАЗОЮ ДАНИХ В ПАМ'ЯТІ ---
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
_TestSessionLocal = async_sessionmaker(_test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Надає асинхронну сесію бази даних для кожного тесту з базою даних у пам'яті.
    Створює таблиці, перевизначає get_db, відкочує зміни та видаляє таблиці.
    Відповідає за відновлення лише своєї власної залежності `get_db`.
    """
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    original_get_db_dependency = app.dependency_overrides.get(get_db)

    current_session = _TestSessionLocal()
    app.dependency_overrides[get_db] = lambda: current_session

    try:
        yield current_session
        await current_session.rollback()
    finally:
        await current_session.close()

        if original_get_db_dependency is None:
            del app.dependency_overrides[get_db]
        else:
            app.dependency_overrides[get_db] = original_get_db_dependency

        async with _test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """
    Надає асинхронний HTTP-клієнт для тестування FastAPI.
    Покладається на інші фікстури, які вже налаштували перевизначення залежностей.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(scope="function")
async def guest_client(client: AsyncClient):
    yield client

@pytest_asyncio.fixture(scope="function")
async def authenticated_user(create_test_user):
    """
    Надає об'єкт UserModel для автентифікованого користувача.
    Цей користувач буде тим же, що використовується для authenticated_user_client,
    якщо клієнт залежатиме від цієї фікстури.
    """
    # Змінено: Передаємо email, потім password, role, а потім username як ключовий аргумент.
    # Також деструктуруємо повернене значення (користувач, токен)
    user_model, _ = await create_test_user(
        "testuser@example.com",
        "UserPass123!",
        UserGroupEnum.USER.value,
        username="TestUser" # <--- Явно вказуємо username
    )
    yield user_model

@pytest_asyncio.fixture(scope="function")
async def authenticated_user_client(client: AsyncClient, authenticated_user: UserModel, jwt_manager: JWTAuthManagerInterface):
    """Надає AsyncClient, автентифікований як звичайний користувач."""
    access_token = await jwt_manager.create_access_token(authenticated_user.id)

    client.headers.update({"Authorization": f"Bearer {access_token}"})
    yield client
    client.headers = {}

@pytest_asyncio.fixture(scope="function")
async def moderator_user(create_test_user) -> UserModel:
    """Надає об'єкт UserModel для модератора."""
    # Змінено: Передаємо email, потім password, role, а потім username як ключовий аргумент.
    # Також деструктуруємо повернене значення (користувач, токен)
    moderator_model, _ = await create_test_user(
        "moderator@example.com",
        "ModeratorPass123!",
        UserGroupEnum.MODERATOR.value,
        username="ModeratorUser" # <--- Явно вказуємо username
    )
    yield moderator_model

@pytest_asyncio.fixture(scope="function")
async def moderator_client(client: AsyncClient, moderator_user: UserModel, jwt_manager: JWTAuthManagerInterface) -> AsyncClient:
    """Надає AsyncClient, автентифікований як модератор."""
    access_token = await jwt_manager.create_access_token(moderator_user.id)
    client.headers.update({"Authorization": f"Bearer {access_token}"})
    yield client
    client.headers = {}


@pytest_asyncio.fixture(scope="function")
async def admin_client(client: AsyncClient, create_test_user):
    # Змінено: Передаємо email, password, role, а потім username як ключовий аргумент.
    user_id, token = await create_test_user(
        "admin@example.com", # <--- Додано email
        "password",
        UserGroupEnum.ADMIN.value, # <--- Використовуємо Enum для ролі
        username="admin" # <--- Явно вказуємо username
    )
    client.headers = {"Authorization": f"Bearer {token}"}
    yield client
    client.headers = {}


@pytest_asyncio.fixture(scope="function")
async def create_test_user(db_session: AsyncSession):
    # Змінено: Додано 'email' як перший позиційний аргумент, 'username' - окремо.
    async def _create_test_user(email: str, password: str, role: str, username: str = None):
        if username is None:
            username = email.split('@')[0] # Автоматично генеруємо username, якщо не надано

        user = UserModel(
            email=email, # Припускаємо, що у вашій UserModel є поле email
            username=username,
            password=password,
            role=role
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        dummy_token = f"dummy_token_for_{user.id}" # Краще генерувати токен від user.id
        return user, dummy_token # Повертаємо об'єкт користувача та токен
    return _create_test_user


# @pytest_asyncio.fixture
# async def async_session():
#     async with TestSessionLocal() as session:
#         yield session
#         await session.rollback()


# @pytest_asyncio.fixture
# async def async_client(async_session):
#     app.dependency_overrides[get_db] = lambda: async_session
#     async with AsyncClient(app=app, base_url="http://test") as client:
#         yield client
#     app.dependency_overrides.clear()