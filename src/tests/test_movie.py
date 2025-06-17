import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, select
import datetime
from decimal import Decimal
from typing import Optional
from unittest.mock import patch, MagicMock

from src.main import app

from src.database.models.base import Base
from src.database.models.movies import (
    MovieModel,
    GenreModel,
    ActorModel,
    CertificationModel
)
from src.database.models.accounts import UserModel, UserGroupModel, UserGroupEnum
from src.database.models.comment import CommentModel
from src.database.models.orders import OrderItem, Order

from src.config.dependencies import get_db, get_current_user, get_current_moderator

TEST_USER: Optional[UserModel] = None
TEST_MODERATOR: Optional[UserModel] = None

mock_send_email_notification = MagicMock()

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=AsyncSession,
                                         expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def test_session():
    global TEST_USER, TEST_MODERATOR

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        user_group = UserGroupModel(name=UserGroupEnum.USER)
        moderator_group = UserGroupModel(name=UserGroupEnum.MODERATOR)
        admin_group = UserGroupModel(
            name=UserGroupEnum.ADMIN)
        session.add_all([user_group, moderator_group, admin_group])
        await session.run_sync(lambda s: s.commit())
        await session.run_sync(lambda s: s.refresh(user_group))
        await session.run_sync(lambda s: s.refresh(moderator_group))
        await session.run_sync(lambda s: s.refresh(admin_group))

        TEST_USER = UserModel.create(email="testuser@example.com", raw_password="Password123!", group_id=user_group.id)
        TEST_MODERATOR = UserModel.create(email="testmoderator@example.com", raw_password="Password123!",
                                          group_id=moderator_group.id)

        session.add_all([TEST_USER, TEST_MODERATOR])
        await session.run_sync(lambda s: s.commit())
        await session.run_sync(lambda s: s.refresh(TEST_USER))
        await session.run_sync(lambda s: s.refresh(TEST_MODERATOR))

        cert = CertificationModel(name="G")
        session.add(cert)
        await session.run_sync(lambda s: s.commit())
        await session.run_sync(lambda s: s.refresh(cert))

        yield session


@pytest.fixture(autouse=True)
def mock_celery_task():
    global mock_send_email_notification
    mock_send_email_notification = MagicMock()
    with patch("src.tasks.send_email_notification", new=mock_send_email_notification):
        yield mock_send_email_notification


@pytest_asyncio.fixture(scope="function")
async def ac(test_session: AsyncSession):
    app.dependency_overrides[get_db] = lambda: test_session

    with TestClient(app=app) as client:
        yield client

    app.dependency_overrides.clear()


async def create_movie_for_tests(session: AsyncSession, cert_id: int, name: str = "Test Movie",
                                 year: int = 2020) -> MovieModel:
    movie = MovieModel(
        name=name, year=year, time=120, imdb=7.5, votes=500, price=Decimal("10.00"),
        description=f"Description for {name}.", certification_id=cert_id
    )
    await session.run_sync(lambda s: s.add(movie))
    await session.run_sync(lambda s: s.commit())
    await session.run_sync(lambda s: s.refresh(movie))
    return movie


async def create_comment_for_tests(session: AsyncSession, user_id: int, movie_id: int, text: str,
                                   parent_id: Optional[int] = None) -> CommentModel:
    comment = CommentModel(user_id=user_id, movie_id=movie_id, text=text, parent_comment_id=parent_id)
    await session.run_sync(lambda s: s.add(comment))
    await session.run_sync(lambda s: s.commit())
    await session.run_sync(lambda s: s.refresh(comment))
    return comment


@pytest.mark.asyncio
async def test_browse_movies_pagination_filter_sort_search(test_session: AsyncSession, ac: TestClient):
    await test_session.run_sync(lambda s: s.refresh(TEST_USER))

    cert_result = await test_session.run_sync(lambda s: s.execute(select(CertificationModel).filter_by(name="G")))
    cert_obj = cert_result.scalars().first()
    assert cert_obj is not None

    movie1 = await create_movie_for_tests(test_session, cert_obj.id, "Action Film", 2022)
    movie2 = await create_movie_for_tests(test_session, cert_obj.id, "Drama Movie", 2023)
    movie3 = await create_movie_for_tests(test_session, cert_obj.id, "SciFi Adventure", 2022)
    movie4 = await create_movie_for_tests(test_session, cert_obj.id, "Another Action", 2023)

    genre_action = GenreModel(name="Action")
    genre_drama = GenreModel(name="Drama")
    genre_scifi = GenreModel(name="Sci-Fi")
    await test_session.run_sync(lambda s: s.add_all([genre_action, genre_drama, genre_scifi]))
    await test_session.run_sync(lambda s: s.commit())
    await test_session.run_sync(lambda s: s.refresh(genre_action))
    await test_session.run_sync(lambda s: s.refresh(genre_drama))
    await test_session.run_sync(lambda s: s.refresh(genre_scifi))

    await test_session.run_sync(lambda s: movie1.genres.append(genre_action))
    await test_session.run_sync(lambda s: movie2.genres.append(genre_drama))
    await test_session.run_sync(lambda s: movie3.genres.append(genre_scifi))
    await test_session.run_sync(lambda s: movie4.genres.append(genre_action))
    await test_session.run_sync(lambda s: s.commit())

    response = ac.get("/api/movies/?page=1&limit=2&sort_by=name&sort_order=asc")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "Action Film"
    assert data[1]["name"] == "Another Action"

    response = ac.get("/api/movies/?year=2023")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert any(m["name"] == "Drama Movie" for m in data)
    assert any(m["name"] == "Another Action" for m in data)

    response = ac.get("/api/movies/?search=Action")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert any(m["name"] == "Action Film" for m in data)
    assert any(m["name"] == "Another Action" for m in data)

    response = ac.get(f"/api/movies/?genre_name={genre_action.name}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert any(m["name"] == "Action Film" for m in data)
    assert any(m["name"] == "Another Action" for m in data)

    movie1.imdb = 8.0
    movie2.imdb = 7.0
    await test_session.run_sync(lambda s: s.commit())
    response = ac.get("/api/movies/?sort_by=imdb&sort_order=asc")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["name"] == "Drama Movie"
    assert data[1]["name"] == "SciFi Adventure"


@pytest.mark.asyncio
async def test_get_movie_details(test_session: AsyncSession, ac: TestClient):
    await test_session.run_sync(lambda s: s.refresh(TEST_USER))

    cert_result = await test_session.run_sync(lambda s: s.execute(select(CertificationModel).filter_by(name="G")))
    cert_obj = cert_result.scalars().first()
    assert cert_obj is not None

    movie = await create_movie_for_tests(test_session, cert_obj.id, "Detailed Movie")
    response = ac.get(f"/api/movies/{movie.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Detailed Movie"
    assert data["description"] == "Description for Detailed Movie."
    assert "genres" in data
    assert "directors" in data
    assert "actors" in data
    assert "certification" in data


@pytest.mark.asyncio
async def test_movie_like_dislike(test_session: AsyncSession, ac: TestClient):
    await test_session.run_sync(lambda s: s.refresh(TEST_USER))

    cert_result = await test_session.run_sync(lambda s: s.execute(select(CertificationModel).filter_by(name="G")))
    cert_obj = cert_result.scalars().first()
    assert cert_obj is not None
    movie = await create_movie_for_tests(test_session, cert_obj.id, "Likeable Movie")

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    try:
        response = ac.post(f"/api/movies/{movie.id}/like?is_liked=true",
                           headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 200
        data = response.json()
        assert data["movie_id"] == movie.id
        assert data["user_id"] == TEST_USER.id
        assert data["is_liked"] is True

        response = ac.post(f"/api/movies/{movie.id}/like?is_liked=true",
                           headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 409

        response = ac.post(f"/api/movies/{movie.id}/like?is_liked=false",
                           headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 200
        data = response.json()
        assert data["is_liked"] is False

        response = ac.post(f"/api/movies/{movie.id}/like?is_liked=false",
                           headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 409
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_add_remove_favorites(test_session: AsyncSession, ac: TestClient):
    await test_session.run_sync(lambda s: s.refresh(TEST_USER))

    cert_result = await test_session.run_sync(lambda s: s.execute(select(CertificationModel).filter_by(name="G")))
    cert_obj = cert_result.scalars().first()
    assert cert_obj is not None
    movie = await create_movie_for_tests(test_session, cert_obj.id, "Favorite Movie")

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    try:
        response = ac.post(f"/api/movies/{movie.id}/favorite", headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["user_id"] == TEST_USER.id
        assert data["movie_id"] == movie.id
        assert "added_at" in data

        response = ac.post(f"/api/movies/{movie.id}/favorite", headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 409

        response = ac.delete(f"/api/movies/{movie.id}/favorite", headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 204

        response = ac.delete(f"/api/movies/{movie.id}/favorite", headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_rate_movie(test_session: AsyncSession, ac: TestClient):
    await test_session.run_sync(lambda s: s.refresh(TEST_USER))

    cert_result = await test_session.run_sync(lambda s: s.execute(select(CertificationModel).filter_by(name="G")))
    cert_obj = cert_result.scalars().first()
    assert cert_obj is not None
    movie = await create_movie_for_tests(test_session, cert_obj.id, "Rateable Movie")

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    try:
        response = ac.post(f"/api/movies/{movie.id}/rate", json={"rating": 8},
                           headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 200
        data = response.json()
        assert data["movie_id"] == movie.id
        assert data["user_id"] == TEST_USER.id
        assert data["rating"] == 8

        response = ac.post(f"/api/movies/{movie.id}/rate", json={"rating": 10},
                           headers={"Authorization": f"Bearer dummy_token"})
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 10
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_moderator_crud_genres(test_session: AsyncSession, ac: TestClient):
    await test_session.run_sync(lambda s: s.refresh(TEST_MODERATOR))

    app.dependency_overrides[get_current_moderator] = lambda: TEST_MODERATOR
    try:
        response = ac.post("/api/movies/genres", json={"name": "New Genre"},
                           headers={"Authorization": f"Bearer dummy_moderator_token"})
        assert response.status_code == 201
        created_genre = response.json()
        assert created_genre["name"] == "New Genre"
        genre_id = None
        if "id" in created_genre:
            genre_id = created_genre["id"]
        else:
            db_genre_query = select(GenreModel).filter_by(name="New Genre")
            db_genre_result = await test_session.execute(db_genre_query)
            db_genre = db_genre_result.scalars().first()
            if db_genre:
                genre_id = db_genre.id
            assert genre_id is not None, "Failed to retrieve genre ID from API response or database."

        response = ac.get("/api/movies/genres")
        assert response.status_code == 200
        genres = response.json()
        assert any(g["name"] == "New Genre" for g in genres)

        response = ac.put(f"/api/movies/genres/{genre_id}", json={"name": "Updated Genre"},
                          headers={"Authorization": f"Bearer dummy_moderator_token"})
        assert response.status_code == 200
        updated_genre = response.json()
        assert updated_genre["name"] == "Updated Genre"

        response = ac.delete(f"/api/movies/genres/{genre_id}",
                             headers={"Authorization": f"Bearer dummy_moderator_token"})
        assert response.status_code == 204

        response = ac.get("/api/movies/genres")
        assert response.status_code == 200
        genres = response.json()
        assert not any(g["name"] == "Updated Genre" for g in genres)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_moderator_crud_actors(test_session: AsyncSession, ac: TestClient):
    await test_session.run_sync(lambda s: s.refresh(TEST_MODERATOR))

    app.dependency_overrides[get_current_moderator] = lambda: TEST_MODERATOR
    try:
        response = ac.post("/api/movies/actors", json={"name": "New Actor"},
                           headers={"Authorization": f"Bearer dummy_moderator_token"})
        assert response.status_code == 201
        created_actor = response.json()
        assert created_actor["name"] == "New Actor"
        actor_id = None
        if "id" in created_actor:
            actor_id = created_actor["id"]
        else:
            db_actor_query = select(ActorModel).filter_by(name="New Actor")
            db_actor_result = await test_session.execute(db_actor_query)
            db_actor = db_actor_result.scalars().first()
            if db_actor:
                actor_id = db_actor.id
            assert actor_id is not None, "Failed to retrieve actor ID from API response or database."

        response = ac.get("/api/movies/actors")
        assert response.status_code == 200
        actors = response.json()
        assert any(a["name"] == "New Actor" for a in actors)

        response = ac.put(f"/api/movies/actors/{actor_id}", json={"name": "Updated Actor"},
                          headers={"Authorization": f"Bearer dummy_moderator_token"})
        assert response.status_code == 200
        updated_actor = response.json()
        assert updated_actor["name"] == "Updated Actor"

        response = ac.delete(f"/api/movies/actors/{actor_id}",
                             headers={"Authorization": f"Bearer dummy_moderator_token"})
        assert response.status_code == 204

        response = ac.get("/api/movies/actors")
        assert response.status_code == 200
        actors = response.json()
        assert not any(a["name"] == "Updated Actor" for a in actors)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_moderator_prevent_movie_deletion_on_purchase(test_session: AsyncSession, ac: TestClient):
    await test_session.run_sync(lambda s: s.refresh(TEST_MODERATOR))
    await test_session.run_sync(lambda s: s.refresh(TEST_USER))

    cert_result = await test_session.run_sync(lambda s: s.execute(select(CertificationModel).filter_by(name="G")))
    cert_obj = cert_result.scalars().first()
    assert cert_obj is not None

    movie = await create_movie_for_tests(test_session, cert_obj.id, "Purchased Movie")

    order = Order(user_id=TEST_USER.id, status="COMPLETED", total_amount=movie.price,
                  created_at=datetime.datetime.now())
    await test_session.run_sync(lambda s: s.add(order))
    await test_session.run_sync(lambda s: s.commit())
    await test_session.run_sync(lambda s: s.refresh(order))

    await test_session.run_sync(
        lambda s: s.add(OrderItem(
            order_id=order.id,
            movie_id=movie.id,
            price_at_order=movie.price
        ))
    )
    await test_session.run_sync(lambda s: s.commit())

    app.dependency_overrides[get_current_moderator] = lambda: TEST_MODERATOR
    try:
        response = ac.delete(f"/api/movies/{movie.id}",
                             headers={"Authorization": f"Bearer dummy_moderator_token"})
        assert response.status_code == 400
        assert response.json()["detail"] == "Cannot delete movie: at least one user has purchased it."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_user_cannot_create_movie(test_session: AsyncSession, ac: TestClient):
    await test_session.run_sync(lambda s: s.refresh(TEST_USER))

    cert_result = await test_session.run_sync(lambda s: s.execute(select(CertificationModel).filter_by(name="G")))
    cert_obj = cert_result.scalars().first()
    assert cert_obj is not None

    movie_data = {
        "name": "Forbidden Film",
        "year": 2024, "time": 90, "imdb": 6.0, "votes": 100, "meta_score": 50,
        "gross": 10.0, "description": "Forbidden.", "price": 5.0,
        "certification_id": cert_obj.id, "genre_ids": [], "director_ids": [], "actor_ids": []
    }
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    try:
        response = ac.post("/api/movies/", json=movie_data, headers={"Authorization": f"Bearer dummy_user_token"})
        assert response.status_code == 403
        assert response.json()["detail"] == "Operation forbidden. Requires moderator role."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_unauthenticated_cannot_create_movie(test_session: AsyncSession, ac: TestClient):
    cert_result = await test_session.run_sync(lambda s: s.execute(select(CertificationModel).filter_by(name="G")))
    cert_obj = cert_result.scalars().first()
    assert cert_obj is not None

    movie_data = {
        "name": "Forbidden Film",
        "year": 2024, "time": 90, "imdb": 6.0, "votes": 100, "meta_score": 50,
        "gross": 10.0, "description": "Forbidden.", "price": 5.0,
        "certification_id": cert_obj.id, "genre_ids": [], "director_ids": [], "actor_ids": []
    }
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_moderator, None)

    try:
        response = ac.post("/api/movies/", json=movie_data)
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"
    finally:
        app.dependency_overrides.clear()
