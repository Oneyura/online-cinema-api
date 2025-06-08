# tests/test_movies.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.movies import (
    MovieModel, GenreModel, DirectorModel, ActorModel, CertificationModel,
    CommentModel, MovieLikeModel, MovieRatingModel, FavoriteMovieModel,
    UserModel, UserRole # Припустимо, що UserRole визначено
)
from src.schemas.movies import MovieCreate, GenreCreate, ActorCreate, DirectorCreate, CertificationCreate
from uuid import uuid4
from datetime import date, datetime
from decimal import Decimal


@pytest.mark.asyncio
async def test_create_certification(moderator_client: AsyncClient, db_session: AsyncSession):
    """Тест створення нової сертифікації модератором."""
    cert_data = {"name": "PG-13"}
    response = await moderator_client.post("/movies/certifications", json=cert_data)

    assert response.status_code == 201
    assert response.json()["name"] == "PG-13"
    assert "id" in response.json()

    # Перевірка, що сертифікація дійсно в БД
    cert_in_db = await db_session.execute(select(CertificationModel).filter_by(name="PG-13"))
    assert cert_in_db.scalars().first() is not None

@pytest.mark.asyncio
async def test_create_certification_duplicate(moderator_client: AsyncClient):
    """Тест створення сертифікації з дублікатом імені."""
    cert_data = {"name": "PG-13"}
    await moderator_client.post("/movies/certifications", json=cert_data) # Перше створення
    response = await moderator_client.post("/movies/certifications", json=cert_data) # Дублікат

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]

@pytest.mark.asyncio
async def test_create_certification_unauthorized(client: AsyncClient):
    """Тест створення сертифікації неавторизованим користувачем (звичаний користувач або гість)."""
    cert_data = {"name": "R"}
    response = await client.post("/movies/certifications", json=cert_data)
    assert response.status_code == 401 # Або 403, залежить від вашої логіки авторизації


@pytest.mark.asyncio
async def test_create_genre(moderator_client: AsyncClient, db_session: AsyncSession):
    """Тест створення нового жанру модератором."""
    genre_data = {"name": "Action"}
    response = await moderator_client.post("/movies/genres", json=genre_data)

    assert response.status_code == 201
    assert response.json()["name"] == "Action"
    assert "id" in response.json()

    genre_in_db = await db_session.execute(select(GenreModel).filter_by(name="Action"))
    assert genre_in_db.scalars().first() is not None

@pytest.mark.asyncio
async def test_create_actor(moderator_client: AsyncClient, db_session: AsyncSession):
    """Тест створення нового актора модератором."""
    actor_data = {"name": "Tom Hanks"}
    response = await moderator_client.post("/movies/actors", json=actor_data)

    assert response.status_code == 201
    assert response.json()["name"] == "Tom Hanks"
    assert "id" in response.json()

    actor_in_db = await db_session.execute(select(ActorModel).filter_by(name="Tom Hanks"))
    assert actor_in_db.scalars().first() is not None

@pytest.mark.asyncio
async def test_create_director(moderator_client: AsyncClient, db_session: AsyncSession):
    """Тест створення нового режисера модератором."""
    director_data = {"name": "Christopher Nolan"}
    response = await moderator_client.post("/movies/directors", json=director_data)

    assert response.status_code == 201
    assert response.json()["name"] == "Christopher Nolan"
    assert "id" in response.json()

    director_in_db = await db_session.execute(select(DirectorModel).filter_by(name="Christopher Nolan"))
    assert director_in_db.scalars().first() is not None


@pytest.mark.asyncio
async def test_create_movie(moderator_client: AsyncClient, db_session: AsyncSession):
    """Тест створення фільму модератором з усіма залежностями."""
    # Створюємо залежності
    await moderator_client.post("/movies/certifications", json={"name": "PG-13"})
    await moderator_client.post("/movies/genres", json={"name": "Sci-Fi"})
    await moderator_client.post("/movies/genres", json={"name": "Thriller"})
    await moderator_client.post("/movies/actors", json={"name": "Leonardo DiCaprio"})
    await moderator_client.post("/movies/actors", json={"name": "Joseph Gordon-Levitt"})
    await moderator_client.post("/movies/directors", json={"name": "Christopher Nolan"})

    # Отримуємо ID створених об'єктів
    cert = await db_session.execute(select(CertificationModel).filter_by(name="PG-13"))
    cert_id = cert.scalars().first().id
    genre_sf = await db_session.execute(select(GenreModel).filter_by(name="Sci-Fi"))
    genre_sf_id = genre_sf.scalars().first().id
    genre_thriller = await db_session.execute(select(GenreModel).filter_by(name="Thriller"))
    genre_thriller_id = genre_thriller.scalars().first().id
    actor_leo = await db_session.execute(select(ActorModel).filter_by(name="Leonardo DiCaprio"))
    actor_leo_id = actor_leo.scalars().first().id
    actor_joseph = await db_session.execute(select(ActorModel).filter_by(name="Joseph Gordon-Levitt"))
    actor_joseph_id = actor_joseph.scalars().first().id
    director_nolan = await db_session.execute(select(DirectorModel).filter_by(name="Christopher Nolan"))
    director_nolan_id = director_nolan.scalars().first().id

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

    # Перевірка, що фільм у БД
    movie_in_db = await db_session.execute(select(MovieModel).filter_by(name="Inception"))
    assert movie_in_db.scalars().first() is not None


@pytest.mark.asyncio
async def test_get_movie_details(moderator_client: AsyncClient, db_session: AsyncSession):
    """Тест отримання деталей фільму."""
    # Створюємо фільм
    cert_id = (await db_session.execute(select(CertificationModel).filter_by(name="PG-13"))).scalars().first().id
    genre_sf_id = (await db_session.execute(select(GenreModel).filter_by(name="Sci-Fi"))).scalars().first().id
    director_nolan_id = (await db_session.execute(select(DirectorModel).filter_by(name="Christopher Nolan"))).scalars().first().id
    actor_leo_id = (await db_session.execute(select(ActorModel).filter_by(name="Leonardo DiCaprio"))).scalars().first().id

    new_movie = MovieModel(
        uuid=uuid4(), name="Test Movie", year=2020, time=120, imdb=7.5, votes=100000,
        description="A test movie.", price=Decimal("5.99"), certification_id=cert_id
    )
    new_movie.genres.append((await db_session.execute(select(GenreModel).filter_by(id=genre_sf_id))).scalars().first())
    new_movie.directors.append((await db_session.execute(select(DirectorModel).filter_by(id=director_nolan_id))).scalars().first())
    new_movie.actors.append((await db_session.execute(select(ActorModel).filter_by(id=actor_leo_id))).scalars().first())
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


@pytest.mark.asyncio
async def test_browse_movies(client: AsyncClient, db_session: AsyncSession):
    """Тест перегляду списку фільмів."""
    # Додаємо кілька фільмів для тестування пагінації та фільтрації
    cert = CertificationModel(name="G")
    db_session.add(cert)
    await db_session.commit()
    await db_session.refresh(cert)

    movie1 = MovieModel(uuid=uuid4(), name="Movie A", year=2020, time=90, imdb=7.0, votes=1000, description="Desc A", price=Decimal("10.00"), certification_id=cert.id)
    movie2 = MovieModel(uuid=uuid4(), name="Movie B", year=2021, time=100, imdb=8.0, votes=2000, description="Desc B", price=Decimal("12.00"), certification_id=cert.id)
    db_session.add_all([movie1, movie2])
    await db_session.commit()

    response = await client.get("/movies?limit=1&page=1")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Movie A" # Або Movie B, залежить від сортування за замовчуванням

    response = await client.get("/movies?search=Movie A")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["name"] == "Movie A"


@pytest.mark.asyncio
async def test_update_movie(moderator_client: AsyncClient, db_session: AsyncSession):
    """Тест оновлення існуючого фільму."""
    # Створюємо залежності та фільм
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


@pytest.mark.asyncio
async def test_delete_movie(moderator_client: AsyncClient, db_session: AsyncSession):
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
    assert response.status_code == 204 # No Content

    # Перевірка, що фільм був видалений з БД
    movie_in_db = await db_session.execute(select(MovieModel).filter_by(id=movie_to_delete.id))
    assert movie_in_db.scalars().first() is None


@pytest.mark.asyncio
async def test_delete_movie_with_purchase(moderator_client: AsyncClient, db_session: AsyncSession, create_test_user):
    """Тест видалення фільму, який був придбаний (має бути заборонено)."""
    user = await create_test_user("buyer@example.com", "buyer")

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

    # Перевірка, що фільм не був видалений
    movie_in_db = await db_session.execute(select(MovieModel).filter_by(id=movie_purchased.id))
    assert movie_in_db.scalars().first() is not None


@pytest.mark.asyncio
async def test_like_movie(authenticated_client: AsyncClient, db_session: AsyncSession):
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

    # Перевірка, що лайк в БД
    like_in_db = await db_session.execute(select(MovieLikeModel).filter_by(movie_id=movie.id))
    assert like_in_db.scalars().first() is not None


@pytest.mark.asyncio
async def test_dislike_movie(authenticated_client: AsyncClient, db_session: AsyncSession):
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

    # Перевірка, що дизлайк в БД
    dislike_in_db = await db_session.execute(select(MovieLikeModel).filter_by(movie_id=movie.id))
    assert dislike_in_db.scalars().first() is not None


@pytest.mark.asyncio
async def test_update_like_status(authenticated_client: AsyncClient, db_session: AsyncSession):
    """Тест оновлення статусу лайка/дизлайка."""
    cert = CertificationModel(name="PG")
    db_session.add(cert)
    await db_session.commit()
    await db_session.refresh(cert)

    movie = MovieModel(uuid=uuid4(), name="Movie for Like Update", year=2024, time=115, imdb=8.0, votes=700, description="Movie to test update.", price=Decimal("10.00"), certification_id=cert.id)
    db_session.add(movie)
    await db_session.commit()
    await db_session.refresh(movie)

    # Спочатку лайк
    await authenticated_client.post(f"/movies/{movie.id}/like?is_liked=true")

    # Потім зміна на дизлайк
    response = await authenticated_client.post(f"/movies/{movie.id}/like?is_liked=false")
    assert response.status_code == 200
    assert response.json()["is_liked"] is False

    # Перевірка, що статус оновився в БД
    like_in_db = await db_session.execute(select(MovieLikeModel).filter_by(movie_id=movie.id))
    assert like_in_db.scalars().first().is_liked is False


@pytest.mark.asyncio
async def test_write_comment(authenticated_client: AsyncClient, db_session: AsyncSession):
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
    assert response.json()["user"]["username"] == "authuser" # Припустимо, що ваш `authenticated_client` використовує "authuser"

    comment_in_db = await db_session.execute(select(CommentModel).filter_by(movie_id=movie.id))
    assert comment_in_db.scalars().first() is not None


@pytest.mark.asyncio
async def test_get_movie_comments(authenticated_client: AsyncClient, db_session: AsyncSession, create_test_user):
    """Тест отримання коментарів до фільму."""
    user1 = await create_test_user("user1@example.com", "UserOne")
    user2 = await create_test_user("user2@example.com", "UserTwo")

    cert = CertificationModel(name="PG")
    db_session.add(cert)
    await db_session.commit()
    await db_session.refresh(cert)

    movie = MovieModel(uuid=uuid4(), name="Movie with Comments", year=2021, time=110, imdb=7.5, votes=600, description="Movie to get comments for.", price=Decimal("11.00"), certification_id=cert.id)
    db_session.add(movie)
    await db_session.commit()
    await db_session.refresh(movie)

    comment1 = CommentModel(user_id=user1.id, movie_id=movie.id, text="Great movie!")
    comment2 = CommentModel(user_id=user2.id, movie_id=movie.id, text="Really enjoyed it.")
    db_session.add_all([comment1, comment2])
    await db_session.commit()

    response = await authenticated_client.get(f"/movies/{movie.id}/comments")
    assert response.status_code == 200
    comments = response.json()
    assert len(comments) == 2
    assert comments[0]["text"] == "Really enjoyed it." # Newest first (descending created_at)
    assert comments[1]["text"] == "Great movie!"
    assert comments[0]["user"]["username"] == "UserTwo"
    assert comments[1]["user"]["username"] == "UserOne"


@pytest.mark.asyncio
async def test_add_movie_to_favorites(authenticated_client: AsyncClient, db_session: AsyncSession):
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

@pytest.mark.asyncio
async def test_remove_movie_from_favorites(authenticated_client: AsyncClient, db_session: AsyncSession, create_test_user):
    """Тест видалення фільму з обраних."""
    user = await create_test_user("favuser@example.com", "FavUser")

    cert = CertificationModel(name="PG")
    db_session.add(cert)
    await db_session.commit()
    await db_session.refresh(cert)

    movie = MovieModel(uuid=uuid4(), name="Unfav Movie", year=2017, time=105, imdb=7.0, votes=400, description="A movie to unfavorite.", price=Decimal("6.00"), certification_id=cert.id)
    db_session.add(movie)
    await db_session.commit()
    await db_session.refresh(movie)

    favorite = FavoriteMovieModel(user_id=user.id, movie_id=movie.id)
    db_session.add(favorite)
    await db_session.commit()

    # Мокаємо get_current_user, щоб він повертав цього користувача
    from main import app
    app.dependency_overrides[app.dependency_overrides[get_current_user]] = lambda: user

    response = await authenticated_client.delete(f"/movies/{movie.id}/favorite")
    assert response.status_code == 204

    fav_in_db = await db_session.execute(select(FavoriteMovieModel).filter_by(movie_id=movie.id, user_id=user.id))
    assert fav_in_db.scalars().first() is None


@pytest.mark.asyncio
async def test_rate_movie(authenticated_client: AsyncClient, db_session: AsyncSession):
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

    rating_in_db = await db_session.execute(select(MovieRatingModel).filter_by(movie_id=movie.id))
    assert rating_in_db.scalars().first() is not None

# Тести для Director та Certification CRUD (за зразком Genre та Actor)
@pytest.mark.asyncio
async def test_create_director_moderator(moderator_client: AsyncClient):
    director_data = {"name": "Ava DuVernay"}
    response = await moderator_client.post("/movies/directors", json=director_data)
    assert response.status_code == 201
    assert response.json()["name"] == "Ava DuVernay"

@pytest.mark.asyncio
async def test_update_director_moderator(moderator_client: AsyncClient, db_session: AsyncSession):
    new_director = DirectorModel(name="Old Director")
    db_session.add(new_director)
    await db_session.commit()
    await db_session.refresh(new_director)

    update_data = {"name": "New Director"}
    response = await moderator_client.put(f"/movies/directors/{new_director.id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["name"] == "New Director"

@pytest.mark.asyncio
async def test_delete_director_moderator(moderator_client: AsyncClient, db_session: AsyncSession):
    new_director = DirectorModel(name="Director to Delete")
    db_session.add(new_director)
    await db_session.commit()
    await db_session.refresh(new_director)

    response = await moderator_client.delete(f"/movies/directors/{new_director.id}")
    assert response.status_code == 204

    director_in_db = await db_session.execute(select(DirectorModel).filter_by(id=new_director.id))
    assert director_in_db.scalars().first() is None


@pytest.mark.asyncio
async def test_update_certification_moderator(moderator_client: AsyncClient, db_session: AsyncSession):
    new_cert = CertificationModel(name="Old Cert")
    db_session.add(new_cert)
    await db_session.commit()
    await db_session.refresh(new_cert)

    update_data = {"name": "New Cert"}
    response = await moderator_client.put(f"/movies/certifications/{new_cert.id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["name"] == "New Cert"

@pytest.mark.asyncio
async def test_delete_certification_moderator(moderator_client: AsyncClient, db_session: AsyncSession):
    new_cert = CertificationModel(name="Cert to Delete")
    db_session.add(new_cert)
    await db_session.commit()
    await db_session.refresh(new_cert)

    response = await moderator_client.delete(f"/movies/certifications/{new_cert.id}")
    assert response.status_code == 204

    cert_in_db = await db_session.execute(select(CertificationModel).filter_by(id=new_cert.id))
    assert cert_in_db.scalars().first() is None
