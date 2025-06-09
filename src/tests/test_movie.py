# tests/test_movies.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from datetime import datetime
from decimal import Decimal

# Впевненість в імпортах: використовуємо абсолютні імпорти
from src.database.models.movies import (
    MovieModel, GenreModel, DirectorModel, ActorModel, CertificationModel,
    CommentModel, MovieLikeModel, MovieRatingModel, FavoriteMovieModel, PurchaseModel
)
from src.database.models.accounts import UserModel
from src.schemas.movies import MovieCreate, GenreCreate, ActorCreate, DirectorCreate, CertificationCreate

# import the app instance from main.py if you need to override dependencies
from src.main import app
from src.config.dependencies import get_current_user # for mocking/overriding get_current_user

# Рекомендується використовувати pytest-asyncio для асинхронних тестів
pytestmark = pytest.mark.asyncio

class TestCertificationCRUD:
    """Група тестів для операцій CRUD над сертифікаціями."""

    async def test_create_certification(self, moderator_client: AsyncClient, db_session: AsyncSession):
        """Тест створення нової сертифікації модератором."""
        cert_data = {"name": "PG-13"}
        response = await moderator_client.post("/movies/certifications", json=cert_data)

        assert response.status_code == 201
        assert response.json()["name"] == "PG-13"
        assert "id" in response.json()

        cert_in_db = await db_session.execute(select(CertificationModel).filter_by(name="PG-13"))
        assert cert_in_db.scalars().first() is not None

    async def test_create_certification_duplicate(self, moderator_client: AsyncClient):
        """Тест створення сертифікації з дублікатом імені."""
        cert_data = {"name": "PG-13"}
        await moderator_client.post("/movies/certifications", json=cert_data)
        response = await moderator_client.post("/movies/certifications", json=cert_data)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    async def test_create_certification_unauthorized(self, client: AsyncClient):
        """Тест створення сертифікації неавторизованим користувачем (звичаний користувач або гість)."""
        cert_data = {"name": "R"}
        response = await client.post("/movies/certifications", json=cert_data)
        assert response.status_code == 401

    async def test_update_certification_moderator(self, moderator_client: AsyncClient, db_session: AsyncSession):
        """Тест оновлення існуючої сертифікації модератором."""
        new_cert = CertificationModel(name="Old Cert")
        db_session.add(new_cert)
        await db_session.commit()
        await db_session.refresh(new_cert)

        update_data = {"name": "New Cert"}
        response = await moderator_client.put(f"/movies/certifications/{new_cert.id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["name"] == "New Cert"

    async def test_delete_certification_moderator(self, moderator_client: AsyncClient, db_session: AsyncSession):
        """Тест видалення сертифікації модератором."""
        new_cert = CertificationModel(name="Cert to Delete")
        db_session.add(new_cert)
        await db_session.commit()
        await db_session.refresh(new_cert)

        response = await moderator_client.delete(f"/movies/certifications/{new_cert.id}")
        assert response.status_code == 204

        cert_in_db = await db_session.execute(select(CertificationModel).filter_by(id=new_cert.id))
        assert cert_in_db.scalars().first() is None


class TestGenreCRUD:
    """Група тестів для операцій CRUD над жанрами."""

    async def test_create_genre(self, moderator_client: AsyncClient, db_session: AsyncSession):
        """Тест створення нового жанру модератором."""
        genre_data = {"name": "Action"}
        response = await moderator_client.post("/movies/genres", json=genre_data)

        assert response.status_code == 201
        assert response.json()["name"] == "Action"
        assert "id" in response.json()

        genre_in_db = await db_session.execute(select(GenreModel).filter_by(name="Action"))
        assert genre_in_db.scalars().first() is not None


class TestActorCRUD:
    """Група тестів для операцій CRUD над акторами."""

    async def test_create_actor(self, moderator_client: AsyncClient, db_session: AsyncSession):
        """Тест створення нового актора модератором."""
        actor_data = {"name": "Tom Hanks"}
        response = await moderator_client.post("/movies/actors", json=actor_data)

        assert response.status_code == 201
        assert response.json()["name"] == "Tom Hanks"
        assert "id" in response.json()

        actor_in_db = await db_session.execute(select(ActorModel).filter_by(name="Tom Hanks"))
        assert actor_in_db.scalars().first() is not None


class TestDirectorCRUD:
    """Група тестів для операцій CRUD над режисерами."""

    async def test_create_director(self, moderator_client: AsyncClient, db_session: AsyncSession):
        """Тест створення нового режисера модератором."""
        director_data = {"name": "Christopher Nolan"}
        response = await moderator_client.post("/movies/directors", json=director_data)

        assert response.status_code == 201
        assert response.json()["name"] == "Christopher Nolan"
        assert "id" in response.json()

        director_in_db = await db_session.execute(select(DirectorModel).filter_by(name="Christopher Nolan"))
        assert director_in_db.scalars().first() is not None

    async def test_create_director_moderator(self, moderator_client: AsyncClient):
        director_data = {"name": "Ava DuVernay"}
        response = await moderator_client.post("/movies/directors", json=director_data)
        assert response.status_code == 201
        assert response.json()["name"] == "Ava DuVernay"

    async def test_update_director_moderator(self, moderator_client: AsyncClient, db_session: AsyncSession):
        new_director = DirectorModel(name="Old Director")
        db_session.add(new_director)
        await db_session.commit()
        await db_session.refresh(new_director)

        update_data = {"name": "New Director"}
        response = await moderator_client.put(f"/movies/directors/{new_director.id}", json=update_data)
        assert response.status_code == 200
        assert response.json()["name"] == "New Director"

    async def test_delete_director_moderator(self, moderator_client: AsyncClient, db_session: AsyncSession):
        new_director = DirectorModel(name="Director to Delete")
        db_session.add(new_director)
        await db_session.commit()
        await db_session.refresh(new_director)

        response = await moderator_client.delete(f"/movies/directors/{new_director.id}")
        assert response.status_code == 204

        director_in_db = await db_session.execute(select(DirectorModel).filter_by(id=new_director.id))
        assert director_in_db.scalars().first() is None


class TestMovieCRUD:
    """Група тестів для операцій CRUD над фільмами."""

    async def test_create_movie(self, moderator_client: AsyncClient, db_session: AsyncSession):
        """Тест створення фільму модератором з усіма залежностями."""
        # Створюємо залежності
        await moderator_client.post("/movies/certifications", json={"name": "PG-13"})
        await moderator_client.post("/movies/genres", json={"name": "Sci-Fi"})
        await moderator_client.post("/movies/genres", json={"name": "Thriller"})
        await moderator_client.post("/movies/actors", json={"name": "Leonardo DiCaprio"})
        await moderator_client.post("/movies/actors", json={"name": "Joseph Gordon-Levitt"})
        await moderator_client.post("/movies/directors", json={"name": "Christopher Nolan"})

        # Отримуємо ID створених об'єктів
        cert = (await db_session.execute(select(CertificationModel).filter_by(name="PG-13"))).scalars().first()
        cert_id = cert.id
        genre_sf = (await db_session.execute(select(GenreModel).filter_by(name="Sci-Fi"))).scalars().first()
        genre_sf_id = genre_sf.id
        genre_thriller = (await db_session.execute(select(GenreModel).filter_by(name="Thriller"))).scalars().first()
        genre_thriller_id = genre_thriller.id
        actor_leo = (await db_session.execute(select(ActorModel).filter_by(name="Leonardo DiCaprio"))).scalars().first()
        actor_leo_id = actor_leo.id
        actor_joseph = (await db_session.execute(select(ActorModel).filter_by(name="Joseph Gordon-Levitt"))).scalars().first()
        actor_joseph_id = actor_joseph.id
        director_nolan = (await db_session.execute(select(DirectorModel).filter_by(name="Christopher Nolan"))).scalars().first()
        director_nolan_id = director_nolan.id

        movie_data = {
            "uuid": str(uuid4()),
            "name": "Inception",
            "year": 2010,
            "time": 148,
            "imdb": 8.8,
            "votes": 2400000,
            "meta_score": 74.0,
            "gross": 292.6,
            "description": "A thief who steals corporate secrets through use of dream-sharing technology.",
            "price": 9.99,
            "certification_id": cert_id,
            "genre_ids": [genre_sf_id, genre_thriller_id],
            "director_ids": [director_nolan_id],
            "star_ids": [actor_leo_id, actor_joseph_id]
        }
        response = await moderator_client.post("/movies", json=movie_data)

        assert response.status_code == 201
        json_response = response.json()
        assert json_response["name"] == "Inception"
        assert json_response["certification"]["name"] == "PG-13"
        assert len(json_response["genres"]) == 2
        assert len(json_response["directors"]) == 1
        assert len(json_response["stars"]) == 2

        movie_in_db = await db_session.execute(select(MovieModel).filter_by(name="Inception"))
        assert movie_in_db.scalars().first() is not None

    async def test_get_movie_details(self, moderator_client: AsyncClient, db_session: AsyncSession):
        """Тест отримання деталей фільму."""
        # Ensure dependencies exist (can be done in a common setup if many tests need them)
        await moderator_client.post("/movies/certifications", json={"name": "PG-13"})
        await moderator_client.post("/movies/genres", json={"name": "Sci-Fi"})
        await moderator_client.post("/movies/directors", json={"name": "Christopher Nolan"})
        await moderator_client.post("/movies/actors", json={"name": "Leonardo DiCaprio"})

        cert = (await db_session.execute(select(CertificationModel).filter_by(name="PG-13"))).scalars().first()
        genre_sf = (await db_session.execute(select(GenreModel).filter_by(name="Sci-Fi"))).scalars().first()
        director_nolan = (await db_session.execute(select(DirectorModel).filter_by(name="Christopher Nolan"))).scalars().first()
        actor_leo = (await db_session.execute(select(ActorModel).filter_by(name="Leonardo DiCaprio"))).scalars().first()

        new_movie = MovieModel(
            uuid=uuid4(), name="Test Movie", year=2020, time=120, imdb=7.5, votes=100000,
            description="A test movie.", price=Decimal("5.99"), certification_id=cert.id
        )
        new_movie.genres.append(genre_sf)
        new_movie.directors.append(director_nolan)
        new_movie.actors.append(actor_leo)
        db_session.add(new_movie)
        await db_session.commit()
        await db_session.refresh(new_movie)

        response = await moderator_client.get(f"/movies/{new_movie.id}")

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["name"] == "Test Movie"
        assert json_response["certification"]["name"] == "PG-13"
        assert len(json_response["genres"]) == 1
        assert json_response["genres"][0]["name"] == "Sci-Fi"
        assert len(json_response["directors"]) == 1
        assert json_response["directors"][0]["name"] == "Christopher Nolan"
        assert len(json_response["stars"]) == 1
        assert json_response["stars"][0]["name"] == "Leonardo DiCaprio"

    async def test_browse_movies(self, client: AsyncClient, db_session: AsyncSession):
        """Тест перегляду списку фільмів."""
        cert = CertificationModel(name="G")
        db_session.add(cert)
        await db_session.commit()
        await db_session.refresh(cert)

        movie1 = MovieModel(uuid=uuid4(), name="Movie A", year=2020, time=90, imdb=7.0, votes=1000, description="Desc A", price=Decimal("10.00"), certification_id=cert.id)
        movie2 = MovieModel(uuid=uuid4(), name="Movie B", year=2021, time=100, imdb=8.0, votes=2000, description="Desc B", price=Decimal("12.00"), certification_id=cert.id)
        db_session.add_all([movie1, movie2])
        await db_session.commit()

        # Test pagination
        response = await client.get("/movies?limit=1&page=1")
        assert response.status_code == 200
        assert len(response.json()) == 1
        # Order might depend on creation time or default sort in API
        assert response.json()[0]["name"] in ["Movie A", "Movie B"]

        # Test search
        response = await client.get("/movies?search=Movie A")
        assert response.status_code == 200
        assert len(response.json()) == 1
        assert response.json()[0]["name"] == "Movie A"

    async def test_update_movie(self, moderator_client: AsyncClient, db_session: AsyncSession):
        """Тест оновлення існуючого фільму."""
        cert1 = CertificationModel(name="PG")
        cert2 = CertificationModel(name="R")
        genre1 = GenreModel(name="Comedy")
        genre2 = GenreModel(name="Drama")
        db_session.add_all([cert1, cert2, genre1, genre2])
        await db_session.commit()
        await db_session.refresh(cert1)
        await db_session.refresh(cert2)
        await db_session.refresh(genre1)
        await db_session.refresh(genre2)

        movie_to_update = MovieModel(
            uuid=uuid4(), name="Old Name", year=2000, time=90, imdb=5.0, votes=100,
            description="Old description", price=Decimal("5.00"), certification_id=cert1.id
        )
        movie_to_update.genres.append(genre1)
        db_session.add(movie_to_update)
        await db_session.commit()
        await db_session.refresh(movie_to_update)

        update_data = {
            "name": "New Name",
            "year": 2005,
            "imdb": 7.0,
            "certification_id": cert2.id,
            "genre_ids": [genre2.id]
        }
        response = await moderator_client.put(f"/movies/{movie_to_update.id}", json=update_data)

        assert response.status_code == 200
        json_response = response.json()
        assert json_response["name"] == "New Name"
        assert json_response["year"] == 2005
        assert json_response["imdb"] == 7.0
        assert json_response["certification"]["name"] == "R"
        assert len(json_response["genres"]) == 1
        assert json_response["genres"][0]["name"] == "Drama"

    async def test_delete_movie(self, moderator_client: AsyncClient, db_session: AsyncSession):
        """Тест видалення фільму модератором."""
        cert = CertificationModel(name="PG")
        db_session.add(cert)
        await db_session.commit()
        await db_session.refresh(cert)

        movie_to_delete = MovieModel(
            uuid=uuid4(), name="Movie to Delete", year=2015, time=100, imdb=6.0, votes=500,
            description="A movie to be deleted.", price=Decimal("7.00"), certification_id=cert.id
        )
        db_session.add(movie_to_delete)
        await db_session.commit()
        await db_session.refresh(movie_to_delete)

        response = await moderator_client.delete(f"/movies/{movie_to_delete.id}")
        assert response.status_code == 204

        movie_in_db = await db_session.execute(select(MovieModel).filter_by(id=movie_to_delete.id))
        assert movie_in_db.scalars().first() is None

    async def test_delete_movie_with_purchase(self, moderator_client: AsyncClient, db_session: AsyncSession, create_test_user):
        """Тест видалення фільму, який був придбаний (має бути заборонено)."""
        user = await create_test_user("buyer@example.com", "buyerpass") # Ensure password is provided for user creation

        cert = CertificationModel(name="PG")
        db_session.add(cert)
        await db_session.commit()
        await db_session.refresh(cert)

        movie_purchased = MovieModel(
            uuid=uuid4(), name="Purchased Movie", year=2018, time=110, imdb=7.8, votes=1000,
            description="Movie that has been purchased.", price=Decimal("15.00"), certification_id=cert.id
        )
        db_session.add(movie_purchased)
        await db_session.commit()
        await db_session.refresh(movie_purchased)

        purchase = PurchaseModel(user_id=user.id, movie_id=movie_purchased.id, purchase_date=datetime.now(), price=Decimal("15.00"))
        db_session.add(purchase)
        await db_session.commit()

        response = await moderator_client.delete(f"/movies/{movie_purchased.id}")
        assert response.status_code == 400
        assert "Cannot delete movie: at least one user has purchased it." in response.json()["detail"]

        movie_in_db = await db_session.execute(select(MovieModel).filter_by(id=movie_purchased.id))
        assert movie_in_db.scalars().first() is not None


class TestMovieInteractions:
    """Група тестів для взаємодії користувачів з фільмами (лайки, коментарі, рейтинги, обрані)."""

    async def test_like_movie(self, authenticated_client: AsyncClient, db_session: AsyncSession):
        """Тест лайка фільму авторизованим користувачем."""
        cert = CertificationModel(name="PG")
        db_session.add(cert)
        await db_session.commit()
        await db_session.refresh(cert)

        movie = MovieModel(uuid=uuid4(), name="Likeable Movie", year=2022, time=95, imdb=7.2, votes=500, description="A movie to like.", price=Decimal("8.99"), certification_id=cert.id)
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        response = await authenticated_client.post(f"/movies/{movie.id}/like?is_liked=true")
        assert response.status_code == 200
        assert response.json()["is_liked"] is True
        assert response.json()["movie_id"] == movie.id

        like_in_db = await db_session.execute(select(MovieLikeModel).filter_by(movie_id=movie.id))
        assert like_in_db.scalars().first() is not None

    async def test_dislike_movie(self, authenticated_client: AsyncClient, db_session: AsyncSession):
        """Тест дизлайка фільму авторизованим користувачем."""
        cert = CertificationModel(name="PG")
        db_session.add(cert)
        await db_session.commit()
        await db_session.refresh(cert)

        movie = MovieModel(uuid=uuid4(), name="Dislikeable Movie", year=2023, time=105, imdb=6.5, votes=300, description="A movie to dislike.", price=Decimal("7.50"), certification_id=cert.id)
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        response = await authenticated_client.post(f"/movies/{movie.id}/like?is_liked=false")
        assert response.status_code == 200
        assert response.json()["is_liked"] is False
        assert response.json()["movie_id"] == movie.id

        dislike_in_db = await db_session.execute(select(MovieLikeModel).filter_by(movie_id=movie.id))
        assert dislike_in_db.scalars().first() is not None

    async def test_update_like_status(self, authenticated_client: AsyncClient, db_session: AsyncSession):
        """Тест оновлення статусу лайка/дизлайка."""
        cert = CertificationModel(name="PG")
        db_session.add(cert)
        await db_session.commit()
        await db_session.refresh(cert)

        movie = MovieModel(uuid=uuid4(), name="Movie for Like Update", year=2024, time=115, imdb=8.0, votes=700, description="Movie to test update.", price=Decimal("10.00"), certification_id=cert.id)
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        await authenticated_client.post(f"/movies/{movie.id}/like?is_liked=true")

        response = await authenticated_client.post(f"/movies/{movie.id}/like?is_liked=false")
        assert response.status_code == 200
        assert response.json()["is_liked"] is False

        like_in_db = await db_session.execute(select(MovieLikeModel).filter_by(movie_id=movie.id))
        assert like_in_db.scalars().first().is_liked is False

    async def test_write_comment(self, authenticated_client: AsyncClient, db_session: AsyncSession, authenticated_user: UserModel):
        """Тест написання коментаря до фільму."""
        cert = CertificationModel(name="PG")
        db_session.add(cert)
        await db_session.commit()
        await db_session.refresh(cert)

        movie = MovieModel(uuid=uuid4(), name="Commentable Movie", year=2020, time=100, imdb=7.0, votes=500, description="A movie for comments.", price=Decimal("9.00"), certification_id=cert.id)
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        comment_data = {"text": "This movie is amazing!"}
        response = await authenticated_client.post(f"/movies/{movie.id}/comments", json=comment_data)

        assert response.status_code == 200
        assert response.json()["text"] == "This movie is amazing!"
        assert response.json()["movie_id"] == movie.id
        assert "user" in response.json()
        assert response.json()["user"]["username"] == authenticated_user.username # Use the actual authenticated user's username

        comment_in_db = await db_session.execute(select(CommentModel).filter_by(movie_id=movie.id, user_id=authenticated_user.id))
        assert comment_in_db.scalars().first() is not None

    async def test_get_movie_comments(self, authenticated_client: AsyncClient, db_session: AsyncSession, create_test_user):
        """Тест отримання коментарів до фільму."""
        user1 = await create_test_user("user1@example.com", "user1pass")
        user2 = await create_test_user("user2@example.com", "user2pass")

        cert = CertificationModel(name="PG")
        db_session.add(cert)
        await db_session.commit()
        await db_session.refresh(cert)

        movie = MovieModel(uuid=uuid4(), name="Movie with Comments", year=2021, time=110, imdb=7.5, votes=600, description="Movie to get comments for.", price=Decimal("11.00"), certification_id=cert.id)
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        # Ensure comments have different creation times to test sorting
        comment1 = CommentModel(user_id=user1.id, movie_id=movie.id, text="Great movie!", created_at=datetime(2023, 1, 1, 10, 0, 0))
        comment2 = CommentModel(user_id=user2.id, movie_id=movie.id, text="Really enjoyed it.", created_at=datetime(2023, 1, 1, 11, 0, 0))
        db_session.add_all([comment1, comment2])
        await db_session.commit()

        response = await authenticated_client.get(f"/movies/{movie.id}/comments")
        assert response.status_code == 200
        comments = response.json()
        assert len(comments) == 2
        # Assuming API returns comments ordered by created_at DESC (newest first)
        assert comments[0]["text"] == "Really enjoyed it."
        assert comments[1]["text"] == "Great movie!"
        assert comments[0]["user"]["username"] == "UserTwo"
        assert comments[1]["user"]["username"] == "UserOne"

    async def test_add_movie_to_favorites(self, authenticated_client: AsyncClient, db_session: AsyncSession):
        """Тест додавання фільму до обраних."""
        cert = CertificationModel(name="PG")
        db_session.add(cert)
        await db_session.commit()
        await db_session.refresh(cert)

        movie = MovieModel(uuid=uuid4(), name="Fav Movie", year=2019, time=120, imdb=8.5, votes=1000, description="A movie for favorites.", price=Decimal("12.00"), certification_id=cert.id)
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        response = await authenticated_client.post(f"/movies/{movie.id}/favorite")
        assert response.status_code == 200
        assert response.json()["movie_id"] == movie.id
        assert "id" in response.json()

        fav_in_db = await db_session.execute(select(FavoriteMovieModel).filter_by(movie_id=movie.id))
        assert fav_in_db.scalars().first() is not None

    async def test_remove_movie_from_favorites(self, authenticated_client: AsyncClient, db_session: AsyncSession, authenticated_user: UserModel):
        """Тест видалення фільму з обраних."""
        # The authenticated_user fixture should provide the user
        user = authenticated_user

        cert = CertificationModel(name="PG")
        db_session.add(cert)
        await db_session.commit()
        await db_session.refresh(cert)

        movie = MovieModel(uuid=uuid4(), name="Unfav Movie", year=2017, time=105, imdb=7.0, votes=400, description="A movie to unfavorite.", price=Decimal("6.00"), certification_id=cert.id)
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        # Add to favorites directly through DB for the test
        favorite = FavoriteMovieModel(user_id=user.id, movie_id=movie.id)
        db_session.add(favorite)
        await db_session.commit()

        # No need to mock get_current_user if authenticated_client is already set up to use authenticated_user
        # app.dependency_overrides[app.dependency_overrides[get_current_user]] = lambda: user # This line is problematic and likely incorrect syntax.

        response = await authenticated_client.delete(f"/movies/{movie.id}/favorite")
        assert response.status_code == 204

        fav_in_db = await db_session.execute(select(FavoriteMovieModel).filter_by(movie_id=movie.id, user_id=user.id))
        assert fav_in_db.scalars().first() is None


    async def test_rate_movie(self, authenticated_client: AsyncClient, db_session: AsyncSession, authenticated_user: UserModel):
        """Тест оцінювання фільму."""
        cert = CertificationModel(name="PG")
        db_session.add(cert)
        await db_session.commit()
        await db_session.refresh(cert)

        movie = MovieModel(uuid=uuid4(), name="Rateable Movie", year=2016, time=130, imdb=7.9, votes=800, description="A movie to rate.", price=Decimal("13.00"), certification_id=cert.id)
        db_session.add(movie)
        await db_session.commit()
        await db_session.refresh(movie)

        rating_data = {"rating": 8}
        response = await authenticated_client.post(f"/movies/{movie.id}/rate", json=rating_data)
        assert response.status_code == 200
        assert response.json()["rating"] == 8
        assert response.json()["movie_id"] == movie.id
        assert response.json()["user_id"] == authenticated_user.id # Assuming user_id is in response

        rating_in_db = await db_session.execute(select(MovieRatingModel).filter_by(movie_id=movie.id, user_id=authenticated_user.id))
        assert rating_in_db.scalars().first() is not None
