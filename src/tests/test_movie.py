from typing import Optional

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, select

# Import your FastAPI app instance
from src.main import app

# Import models and dependencies
from src.database.models.base import Base  # Базовий клас для моделей SQLAlchemy
from src.database.models.movies import MovieModel, GenreModel, DirectorModel, ActorModel, CertificationModel, \
    MovieLikeModel, MovieRatingModel, FavoriteMovieModel
from src.database.models.accounts import UserModel, UserGroupModel, \
    UserGroupEnum  # Імпортуємо UserModel та UserGroupModel, UserGroupEnum

from src.database.models.comment import CommentModel

from src.config.dependencies import get_db, get_current_user, get_current_moderator  # get_current_admin

# Глобальні змінні для тестових користувачів, які будуть встановлені у фікстурі
# Ініціалізуємо як None, вони будуть заповнені у фікстурі test_session
TEST_USER: Optional[UserModel] = None
TEST_MODERATOR: Optional[UserModel] = None
TEST_ADMIN: Optional[UserModel] = None

# region Mock Dependencies
# Mock database engine and session for testing
DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession)


# Фікстура для налаштування тестової бази даних та тестових користувачів
# Ця фікстура буде виконуватися один раз для кожного тесту (scope="function" за замовчуванням)
# і забезпечить чисте середовище для кожного тесту.
@pytest.fixture(scope="function")  # Явно вказуємо scope="function"
async def test_session():
    global TEST_USER, TEST_MODERATOR, TEST_ADMIN  # Дозволяємо змінювати глобальні змінні

    # 1. Створення таблиць
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Використання сесії для заповнення початкових даних (груп користувачів, тестових користувачів, сертифікації)
    async with TestingSessionLocal() as session_for_setup:
        # Створюємо групи користувачів
        user_group = UserGroupModel(name=UserGroupEnum.USER)
        moderator_group = UserGroupModel(name=UserGroupEnum.MODERATOR)
        admin_group = UserGroupModel(name=UserGroupEnum.ADMIN)
        session_for_setup.add_all([user_group, moderator_group, admin_group])
        await session_for_setup.commit()
        await session_for_setup.refresh(user_group)
        await session_for_setup.refresh(moderator_group)
        await session_for_setup.refresh(admin_group)

        # Створюємо тестових користувачів за допомогою фабричного методу UserModel.create
        TEST_USER = UserModel.create(email="testuser@example.com", raw_password="password123", group_id=user_group.id)
        TEST_MODERATOR = UserModel.create(email="testmoderator@example.com", raw_password="password123",
                                          group_id=moderator_group.id)
        TEST_ADMIN = UserModel.create(email="testadmin@example.com", raw_password="password123",
                                      group_id=admin_group.id)

        session_for_setup.add_all([TEST_USER, TEST_MODERATOR, TEST_ADMIN])
        await session_for_setup.commit()
        await session_for_setup.refresh(TEST_USER)
        await session_for_setup.refresh(TEST_MODERATOR)
        await session_for_setup.refresh(TEST_ADMIN)

        # Створення CertificationModel для тестів, які цього потребують
        # Встановлюємо ID вручну, якщо потрібно, щоб воно було певним значенням (наприклад, 1)
        # або просто дозволяємо автоінкремент і використовуємо отриманий ID.
        # Для простоти, якщо ID не 1, попередження.
        cert = CertificationModel(name="G")
        session_for_setup.add(cert)
        await session_for_setup.commit()
        await session_for_setup.refresh(cert)

        if cert.id != 1:
            print(f"Warning: Default Certification ID is {cert.id}, not 1. Some tests might fail.")

    # 3. Yielding the AsyncSession for the actual test function to use
    # Це створює нову сесію для кожного тесту, забезпечуючи ізоляцію.
    async with TestingSessionLocal() as session_for_test:
        yield session_for_test  # THIS is the AsyncSession that will be passed to test functions

    # 4. Очищення після тестів (скидання всіх таблиць)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# Override get_db dependency for FastAPI
# Ця фікстура отримує вже ініціалізовану test_session з попередньої фікстури
@pytest.fixture
def override_get_db(test_session: AsyncSession):
    async def _override_get_db():
        yield test_session  # Yield the session provided by test_session fixture

    return _override_get_db


# Override get_current_user dependency for FastAPI
@pytest.fixture
def override_get_current_user():
    async def _override_get_current_user():
        if TEST_USER is None:
            raise Exception("TEST_USER not initialized in test_session_fixture.")
        return TEST_USER

    return _override_get_current_user


# Override get_current_moderator dependency for FastAPI
@pytest.fixture
def override_get_current_moderator():
    async def _override_get_current_moderator():
        if TEST_MODERATOR is None:
            raise Exception("TEST_MODERATOR not initialized in test_session_fixture.")
        return TEST_MODERATOR

    return _override_get_current_moderator


# Apply overrides to the FastAPI app
# ВАЖЛИВО: ВИДАЛЕНО pytest.fixture(scope="function")(...) з цих призначень
# Оскільки override_get_db_fixture вже є фікстурою, ми просто призначаємо її.
app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user
app.dependency_overrides[get_current_moderator] = override_get_current_moderator


# endregion

@pytest.mark.asyncio
async def test_create_movie_and_get_details(test_session: AsyncSession):
    # Setup initial data for related models (Certification, Genre, Director, Actor)
    # This is required because MovieCreate has foreign key dependencies
    # Certification 'G' should already be in test_session from test_session_fixture
    cert = await test_session.execute(select(CertificationModel).filter_by(name="G"))
    cert = cert.scalars().first()
    assert cert is not None  # Перевіряємо, що сертифікація дійсно існує

    genre = GenreModel(name="Action")
    director = DirectorModel(name="Christopher Nolan")
    actor = ActorModel(name="Leonardo DiCaprio")

    test_session.add_all([genre, director, actor])
    await test_session.commit()
    await test_session.refresh(genre)
    await test_session.refresh(director)
    await test_session.refresh(actor)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        movie_data = {
            "name": "Inception Test",
            "year": 2010,
            "time": 148,
            "imdb": 8.8,
            "votes": 2400000,
            "meta_score": 74,
            "gross": 292.6,
            "description": "A thief who steals corporate secrets through dream-sharing technology.",
            "price": 9.99,
            "certification_id": cert.id,  # Використовуємо ID створеної сертифікації
            "genre_ids": [genre.id],
            "director_ids": [director.id],
            "actor_ids": [actor.id]
        }
        # The /movies/ endpoint requires a moderator token or dependency
        response = await ac.post("/movies/", json=movie_data, headers={"Authorization": "Bearer dummy_moderator_token"})
        assert response.status_code == 201, response.text
        created_movie = response.json()
        assert created_movie["name"] == movie_data["name"]
        assert created_movie["certification"]["id"] == cert.id
        assert len(created_movie["genres"]) == 1
        assert created_movie["genres"][0]["id"] == genre.id

        movie_id = created_movie["id"]

        # Test getting movie details
        response = await ac.get(f"/movies/{movie_id}")
        assert response.status_code == 200, response.text
        fetched_movie = response.json()
        assert fetched_movie["name"] == "Inception Test"
        assert fetched_movie["id"] == movie_id
        assert fetched_movie["certification"]["name"] == "G"  # Перевіряємо за ім'ям, яке створили
        assert fetched_movie["genres"][0]["name"] == "Action"
        assert fetched_movie["directors"][0]["name"] == "Christopher Nolan"
        assert fetched_movie["actors"][0]["name"] == "Leonardo DiCaprio"


@pytest.mark.asyncio
async def test_get_movie_comments_no_comments(test_session: AsyncSession):
    # Створити фільм, щоб мати існуючий movie_id
    # Certification 'G' should already be in test_session from test_session_fixture
    cert = await test_session.execute(select(CertificationModel).filter_by(name="G"))
    cert = cert.scalars().first()
    assert cert is not None

    movie = MovieModel(
        name="Movie Without Comments", year=2023, time=90, imdb=7.0, votes=100, price=5.0,
        description="A movie without comments.", certification_id=cert.id
    )
    test_session.add(movie)
    await test_session.commit()
    await test_session.refresh(movie)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(f"/movies/{movie.id}/comments")
        assert response.status_code == 200
        assert response.json() == []


@pytest.mark.asyncio
async def test_get_movie_comments_movie_not_found(test_session: AsyncSession):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/movies/99999/comments")
        assert response.status_code == 404
        assert response.json()["detail"] == "Movie not found"


@pytest.mark.asyncio
async def test_write_comment_success(test_session: AsyncSession):
    # Створити фільм та користувача для коментаря
    # Certification 'G' should already be in test_session from test_session_fixture
    cert = await test_session.execute(select(CertificationModel).filter_by(name="G"))
    cert = cert.scalars().first()
    assert cert is not None

    movie = MovieModel(
        name="Comment Test Movie", year=2020, time=120, imdb=7.5, votes=500, price=10.0,
        description="A movie for comments.", certification_id=cert.id
    )
    # TEST_USER вже додано та оновлено в test_session_fixture
    test_session.add(movie)
    await test_session.commit()
    await test_session.refresh(movie)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        comment_data = {"text": "This is a great movie!"}
        # Використовуємо тестовий токен, який відповідає TEST_USER
        response = await ac.post(f"/movies/{movie.id}/comments", json=comment_data,
                                 headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 201, response.text
        created_comment = response.json()
        assert created_comment["text"] == comment_data["text"]
        assert created_comment["movie_id"] == movie.id
        assert created_comment["user_id"] == TEST_USER.id  # Перевіряємо ID
        assert created_comment["parent_comment_id"] is None
        assert "user" in created_comment
        assert created_comment["user"]["id"] == TEST_USER.id
        assert created_comment["user"]["email"] == TEST_USER.email


@pytest.mark.asyncio
async def test_write_reply_to_comment_success(test_session: AsyncSession):
    # Створити фільм та користувача
    # Certification 'G' should already be in test_session from test_session_fixture
    cert = await test_session.execute(select(CertificationModel).filter_by(name="G"))
    cert = cert.scalars().first()
    assert cert is not None

    movie = MovieModel(
        name="Reply Test Movie", year=2021, time=100, imdb=8.0, votes=600, price=11.0,
        description="Movie for replies.", certification_id=cert.id
    )
    # TEST_USER вже додано та оновлено в test_session_fixture
    test_session.add(movie)
    await test_session.commit()
    await test_session.refresh(movie)

    # Створити батьківський коментар
    parent_comment = CommentModel(
        user_id=TEST_USER.id, movie_id=movie.id, text="Original comment."
    )
    test_session.add(parent_comment)
    await test_session.commit()
    await test_session.refresh(parent_comment)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        reply_data = {
            "text": "This is a reply!",
            "parent_comment_id": parent_comment.id
        }
        response = await ac.post(f"/movies/{movie.id}/comments", json=reply_data,
                                 headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 201
        created_reply = response.json()
        assert created_reply["text"] == reply_data["text"]
        assert created_reply["movie_id"] == movie.id
        assert created_reply["user_id"] == TEST_USER.id
        assert created_reply["parent_comment_id"] == parent_comment.id
        assert "user" in created_reply
        assert created_reply["user"]["id"] == TEST_USER.id
        assert created_reply["user"]["email"] == TEST_USER.email


@pytest.mark.asyncio
async def test_write_comment_movie_not_found(test_session: AsyncSession):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        comment_data = {"text": "Should not be added."}
        response = await ac.post("/movies/99999/comments", json=comment_data,
                                 headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Movie not found"


@pytest.mark.asyncio
async def test_write_reply_parent_comment_not_found(test_session: AsyncSession):
    # Створити фільм
    # Certification 'G' should already be in test_session from test_session_fixture
    cert = await test_session.execute(select(CertificationModel).filter_by(name="G"))
    cert = cert.scalars().first()
    assert cert is not None

    movie = MovieModel(
        name="Invalid Reply Test Movie", year=2022, time=110, imdb=6.5, votes=300, price=8.0,
        description="Movie for invalid replies.", certification_id=cert.id
    )
    test_session.add(movie)
    await test_session.commit()
    await test_session.refresh(movie)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        reply_data = {
            "text": "Reply to non-existent parent.",
            "parent_comment_id": 99999
        }
        response = await ac.post(f"/movies/{movie.id}/comments", json=reply_data,
                                 headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Parent comment with ID 99999 not found."


@pytest.mark.asyncio
async def test_get_movie_comments_with_replies(test_session: AsyncSession):
    # Створити фільм та кількох користувачів
    # Certification 'G' should already be in test_session from test_session_fixture
    cert = await test_session.execute(select(CertificationModel).filter_by(name="G"))
    cert = cert.scalars().first()
    assert cert is not None

    movie = MovieModel(
        name="Complex Comments Movie", year=2023, time=150, imdb=8.5, votes=1000, price=15.0,
        description="A movie with complex comments.", certification_id=cert.id
    )
    user1 = TEST_USER
    # Створюємо користувачів 2 та 3 через SQLAlchemy, щоб вони мали Group
    user2 = UserModel.create(email="user2@example.com", raw_password="password123", group_id=(
        await test_session.execute(select(UserGroupModel).filter_by(name=UserGroupEnum.USER))).scalars().first().id)
    user3 = UserModel.create(email="user3@example.com", raw_password="password123", group_id=(
        await test_session.execute(select(UserGroupModel).filter_by(name=UserGroupEnum.USER))).scalars().first().id)

    test_session.add_all([movie, user2, user3])  # user1 вже додано
    await test_session.commit()
    await test_session.refresh(movie)
    await test_session.refresh(user1)
    await test_session.refresh(user2)
    await test_session.refresh(user3)

    # Створити коментарі:
    # Top-level comment 1 (by user1)
    comment1 = CommentModel(user_id=user1.id, movie_id=movie.id, text="Top comment 1.")
    # Top-level comment 2 (by user2)
    comment2 = CommentModel(user_id=user2.id, movie_id=movie.id, text="Top comment 2.")
    test_session.add_all([comment1, comment2])
    await test_session.commit()
    await test_session.refresh(comment1)
    await test_session.refresh(comment2)

    # Reply to comment 1 (by user3)
    reply1_to_1 = CommentModel(user_id=user3.id, movie_id=movie.id, text="Reply to C1.", parent_comment_id=comment1.id)
    test_session.add(reply1_to_1)
    await test_session.commit()
    await test_session.refresh(reply1_to_1)

    # Reply to reply1_to_1 (by user1)
    reply1_to_reply1 = CommentModel(user_id=user1.id, movie_id=movie.id, text="Reply to R1.",
                                    parent_comment_id=reply1_to_1.id)
    test_session.add(reply1_to_reply1)
    await test_session.commit()
    await test_session.refresh(reply1_to_reply1)

    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get(f"/movies/{movie.id}/comments")
        assert response.status_code == 200
        comments = response.json()

        # Перевіряємо кількість верхньорівневих коментарів
        assert len(comments) == 2

        # Перевіряємо comment1
        c1 = next((c for c in comments if c["id"] == comment1.id), None)
        assert c1 is not None
        assert c1["text"] == "Top comment 1."
        assert c1["user_id"] == user1.id
        assert c1["movie_id"] == movie.id
        assert c1["user"]["email"] == user1.email  # Перевіряємо, що вкладений користувач є

        # Перевіряємо reply1_to_1 (відповідь на comment1)
        assert len(c1["replies"]) == 1
        r1_to_1 = c1["replies"][0]
        assert r1_to_1["id"] == reply1_to_1.id
        assert r1_to_1["text"] == "Reply to C1."
        assert r1_to_1["parent_comment_id"] == comment1.id
        assert r1_to_1["user_id"] == user3.id
        assert r1_to_1["user"]["email"] == user3.email

        # Перевіряємо reply1_to_reply1 (відповідь на reply1_to_1)
        assert len(r1_to_1["replies"]) == 1
        r1_to_r1 = r1_to_1["replies"][0]
        assert r1_to_r1["id"] == reply1_to_reply1.id
        assert r1_to_r1["text"] == "Reply to R1."
        assert r1_to_r1["parent_comment_id"] == reply1_to_1.id
        assert r1_to_r1["user_id"] == user1.id
        assert r1_to_r1["user"]["email"] == user1.email

        # Перевіряємо comment2
        c2 = next((c for c in comments if c["id"] == comment2.id), None)
        assert c2 is not None
        assert c2["text"] == "Top comment 2."
        assert c2["user_id"] == user2.id
        assert c2["movie_id"] == movie.id
        assert c2["user"]["email"] == user2.email
        assert len(c2["replies"]) == 0


@pytest.mark.asyncio
async def test_get_movie_comments_pagination(test_session: AsyncSession):
    # Створити фільм та користувача
    # Certification 'G' should already be in test_session from test_session_fixture
    cert = await test_session.execute(select(CertificationModel).filter_by(name="G"))
    cert = cert.scalars().first()
    assert cert is not None

    movie = MovieModel(
        name="Pagination Movie", year=2024, time=110, imdb=7.8, votes=700, price=12.0,
        description="Movie for pagination tests.", certification_id=cert.id
    )
    # TEST_USER вже додано та оновлено в test_session_fixture
    test_session.add(movie)
    await test_session.commit()
    await test_session.refresh(movie)

    # Створити 25 коментарів
    for i in range(1, 26):
        comment = CommentModel(user_id=TEST_USER.id, movie_id=movie.id, text=f"Comment {i}")
        test_session.add(comment)
    await test_session.commit()

    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Page 1, limit 10
        response = await ac.get(f"/movies/{movie.id}/comments?page=1&limit=10")
        assert response.status_code == 200
        comments = response.json()
        assert len(comments) == 10
        assert comments[0]["text"] == "Comment 25"  # Order by created_at desc
        assert comments[9]["text"] == "Comment 16"

        # Page 2, limit 10
        response = await ac.get(f"/movies/{movie.id}/comments?page=2&limit=10")
        assert response.status_code == 200
        comments = response.json()
        assert len(comments) == 10
        assert comments[0]["text"] == "Comment 15"
        assert comments[9]["text"] == "Comment 6"

        # Page 3, limit 10 (should have 5 comments)
        response = await ac.get(f"/movies/{movie.id}/comments?page=3&limit=10")
        assert response.status_code == 200
        comments = response.json()
        assert len(comments) == 5
        assert comments[0]["text"] == "Comment 5"
        assert comments[4]["text"] == "Comment 1"

        # Page 4, limit 10 (should be empty)
        response = await ac.get(f"/movies/{movie.id}/comments?page=4&limit=10")
        assert response.status_code == 200
        assert response.json() == []
