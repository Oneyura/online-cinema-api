import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select, and_
from uuid import uuid4
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from src.main import app
from src.config.dependencies import get_db, get_current_user

# Імпортуємо моделі
from src.database.models.orders import Order, OrderItem, OrderStatusEnum
from src.database.models.movies import (
    MovieModel, GenreModel, DirectorModel, ActorModel, CertificationModel,
    MovieLikeModel, MovieRatingModel, FavoriteMovieModel
)
from src.database.models.accounts import UserModel, UserGroupModel, UserGroupEnum
from src.database.models.comment import CommentModel
from src.database.models.cart import CartModel, CartItemModel

pytestmark = pytest.mark.asyncio

# --- Глобальні сховища мокових даних в пам'яті та лічильник ID ---
_mock_id_counter = 1
_mock_certifications = []
_mock_genres = []
_mock_directors = []
_mock_actors = []
_mock_movies = []
_mock_movie_likes = []
_mock_movie_ratings = []
_mock_favorite_movies = []
_mock_comments = []
_mock_users = []
_mock_orders = []
_mock_order_items = []
_mock_carts = []
_mock_cart_items = []


def _generate_id():
    """Генерує унікальний ID для мокових об'єктів."""
    global _mock_id_counter
    _id = _mock_id_counter
    _mock_id_counter += 1
    return _id


# --- Допоміжна функція для створення мокових результатів execute ---
def create_mock_result(value):
    mock_result = MagicMock()

    class MockScalars:
        def first(self_inner):
            if isinstance(value, list):
                return value[0] if value else None
            return value

        def all(self_inner):
            if isinstance(value, list):
                return value
            return [value] if value is not None else []

    mock_result.scalars.return_value = MockScalars()
    mock_result.first.return_value = MockScalars().first()
    return mock_result


# --- ГЛОБАЛЬНА ДОПОМІЖНА ФУНКЦІЯ ДЛЯ ДОДАВАННЯ ---
async def _single_add_logic(instance):
    """
    Допоміжна функція для імітації додавання об'єкта до відповідного глобального мокового сховища.
    """
    if not hasattr(instance, 'id') or instance.id is None:
        instance.id = _generate_id()

    if isinstance(instance, CertificationModel):
        _mock_certifications.append(instance)
    elif isinstance(instance, GenreModel):
        _mock_genres.append(instance)
    elif isinstance(instance, DirectorModel):
        _mock_directors.append(instance)
    elif isinstance(instance, ActorModel):
        _mock_actors.append(instance)
    elif isinstance(instance, MovieModel):
        _mock_movies.append(instance)
    elif isinstance(instance, MovieLikeModel):
        _mock_movie_likes.append(instance)
    elif isinstance(instance, MovieRatingModel):
        _mock_movie_ratings.append(instance)
    elif isinstance(instance, FavoriteMovieModel):
        _mock_favorite_movies.append(instance)
    elif isinstance(instance, CommentModel):
        _mock_comments.append(instance)
    elif isinstance(instance, UserModel):
        _mock_users.append(instance)
    elif isinstance(instance, Order):
        _mock_orders.append(instance)
    elif isinstance(instance, OrderItem):
        _mock_order_items.append(instance)
    elif isinstance(instance, CartModel):
        _mock_carts.append(instance)
    elif isinstance(instance, CartItemModel):
        _mock_cart_items.append(instance)


# --- Фікстури для мокових даних та сесії БД ---

@pytest.fixture
def mock_db():
    """Фікстура, яка надає моковану AsyncSession для тестів."""
    global _mock_id_counter
    _mock_id_counter = 1
    _mock_certifications.clear()
    _mock_genres.clear()
    _mock_directors.clear()
    _mock_actors.clear()
    _mock_movies.clear()
    _mock_movie_likes.clear()
    _mock_movie_ratings.clear()
    _mock_favorite_movies.clear()
    _mock_comments.clear()
    _mock_users.clear()
    _mock_orders.clear()
    _mock_order_items.clear()
    _mock_carts.clear()
    _mock_cart_items.clear()

    db = AsyncMock(spec=AsyncSession)

    # --- Імітація add та add_all ---
    async def mock_add_or_all(instance_or_list):
        if isinstance(instance_or_list, list):
            for instance in instance_or_list:
                await _single_add_logic(instance)
        else:
            await _single_add_logic(instance_or_list)

    db.add.side_effect = mock_add_or_all
    db.add_all.side_effect = mock_add_or_all

    # --- Імітація commit ---
    db.commit.return_value = None

    # --- Імітація flush ---
    async def mock_flush_effect():
        pass

    db.flush.side_effect = mock_flush_effect

    # --- Імітація refresh ---
    async def mock_refresh(instance):
        if isinstance(instance, MovieModel):
            instance.certification = next((c for c in _mock_certifications if c.id == instance.certification_id), None)
            instance.genres = [g for g in _mock_genres if g.id in getattr(instance, '_mock_genre_ids', [])]
            instance.directors = [d for d in _mock_directors if d.id in getattr(instance, '_mock_director_ids', [])]
            instance.actors = [a for a in _mock_actors if a.id in getattr(instance, '_mock_actor_ids', [])]
        elif isinstance(instance, Order):
            instance.items = [item for item in _mock_order_items if item.order_id == instance.id]
        elif isinstance(instance, OrderItem):
            instance.movie = next((m for m in _mock_movies if m.id == instance.movie_id), None)
        elif isinstance(instance, CommentModel):
            instance.user = next((u for u in _mock_users if u.id == instance.user_id), None)
            instance.movie = next((m for m in _mock_movies if m.id == instance.movie_id), None)
            instance.replies = [c for c in _mock_comments if c.parent_comment_id == instance.id]
        return instance

    db.refresh.side_effect = mock_refresh

    # --- Імітація delete ---
    async def mock_delete(instance):
        if isinstance(instance, CertificationModel):
            _mock_certifications[:] = [c for c in _mock_certifications if c.id != instance.id]
        elif isinstance(instance, MovieModel):
            _mock_movies[:] = [m for m in _mock_movies if m.id != instance.id]

    db.delete.side_effect = mock_delete

    # --- Імітація execute ---
    async def mock_execute(statement):
        model_class = None
        if hasattr(statement, 'element') and hasattr(statement.element, 'selectable') and hasattr(
                statement.element.selectable, 'class_'):
            model_class = statement.element.selectable.class_
        elif hasattr(statement, 'entity_description') and hasattr(statement.entity_description, 'entity'):
            model_class = statement.entity_description.entity

        data_store = []
        if model_class == CertificationModel:
            data_store = _mock_certifications
        elif model_class == GenreModel:
            data_store = _mock_genres
        elif model_class == DirectorModel:
            data_store = _mock_directors
        elif model_class == ActorModel:
            data_store = _mock_actors
        elif model_class == MovieModel:
            data_store = _mock_movies
        elif model_class == MovieLikeModel:
            data_store = _mock_movie_likes
        elif model_class == MovieRatingModel:
            data_store = _mock_movie_ratings
        elif model_class == FavoriteMovieModel:
            data_store = _mock_favorite_movies
        elif model_class == CommentModel:
            data_store = _mock_comments
        elif model_class == UserModel:
            data_store = _mock_users
        elif model_class == UserGroupModel:
            data_store = [
                UserGroupModel(id=1, name=UserGroupEnum.ADMIN),
                UserGroupModel(id=2, name=UserGroupEnum.USER),
                UserGroupModel(id=3, name=UserGroupEnum.MODERATOR)
            ]
        elif model_class == Order:
            data_store = _mock_orders
        elif model_class == OrderItem:
            data_store = _mock_order_items
        elif model_class == CartModel:
            data_store = _mock_carts
        elif model_class == CartItemModel:
            data_store = _mock_cart_items

        results = list(data_store)

        if hasattr(statement.element, 'whereclause') and statement.element.whereclause is not None:
            try:
                from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList
                if isinstance(statement.element.whereclause, BinaryExpression):
                    filter_key = statement.element.whereclause.left.key
                    filter_value = statement.element.whereclause.right.value

                    results = [item for item in results if getattr(item, filter_key, None) == filter_value]

                elif isinstance(statement.element.whereclause, BooleanClauseList):
                    temp_results = []
                    for item in data_store:
                        match = True
                        for clause in statement.element.whereclause.clauses:
                            if hasattr(clause, 'left') and hasattr(clause.left, 'key') and hasattr(clause.right, 'value'):
                                filter_key = clause.left.key
                                filter_value = clause.right.value
                                if not (hasattr(item, filter_key) and getattr(item, filter_key) == filter_value):
                                    match = False
                                    break
                        if match:
                            temp_results.append(item)
                    results = temp_results

            except Exception as e:
                pass

        return create_mock_result(results)

    db.execute.side_effect = mock_execute

    yield db


# --- Перевизначення залежностей FastAPI ---
@pytest.fixture(autouse=True)
def override_get_db(mock_db):
    """Перевизначає залежність get_db FastAPI для використання мок-сесії."""
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.clear()


# Змінено: ця фікстура має бути звичайним генератором, якщо ми хочемо її await-ити в інших.
# Або, якщо ви хочете, щоб вона була асинхронною, то інші фікстури повинні її `await`
# Давайте спробуємо зробити її асинхронною і явно `await` її в інших.
@pytest.fixture
async def client():
    """Фікстура, яка надає TestClient для FastAPI додатка (для неавторизованих запитів)."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


# --- Змінені фікстури аутентифікованих клієнтів ---

# Використовуємо pytest_asyncio.fixture для гарантованого розгортання
@pytest_asyncio.fixture
async def authenticated_user_client(mock_db: AsyncSession, client: AsyncClient):
    """
    Клієнт, що імітує аутентифікованого звичайного користувача.
    """
    user_group = next((g for g in _mock_users if isinstance(g, UserGroupModel) and g.name == UserGroupEnum.USER), None)
    if not user_group:
        user_group = UserGroupModel(id=_generate_id(), name=UserGroupEnum.USER)
        _mock_users.append(user_group)

    user = UserModel(id=_generate_id(), email="authenticated@example.com", _hashed_password="hashed_pass",
                     is_active=True, group_id=user_group.id)
    user.group = user_group
    _mock_users.append(user)

    app.dependency_overrides[get_current_user] = lambda: user
    yield client
    app.dependency_overrides.pop(get_current_user)


@pytest_asyncio.fixture
async def moderator_client(mock_db: AsyncSession, client: AsyncClient):
    """
    Клієнт, що імітує аутентифікованого модератора.
    """
    mod_group = next((g for g in _mock_users if isinstance(g, UserGroupModel) and g.name == UserGroupEnum.MODERATOR),
                     None)
    if not mod_group:
        mod_group = UserGroupModel(id=_generate_id(), name=UserGroupEnum.MODERATOR)
        _mock_users.append(mod_group)

    mod_user = UserModel(id=_generate_id(), email="moderator@example.com", _hashed_password="hashed_pass",
                         is_active=True, group_id=mod_group.id)
    mod_user.group = mod_group
    _mock_users.append(mod_user)

    app.dependency_overrides[get_current_user] = lambda: mod_user
    yield client
    app.dependency_overrides.pop(get_current_user)


@pytest_asyncio.fixture
async def admin_client(mock_db: AsyncSession, client: AsyncClient):
    """
    Клієнт, що імітує аутентифікованого адміністратора.
    """
    admin_group = next((g for g in _mock_users if isinstance(g, UserGroupModel) and g.name == UserGroupEnum.ADMIN),
                       None)
    if not admin_group:
        admin_group = UserGroupModel(id=_generate_id(), name=UserGroupEnum.ADMIN)
        _mock_users.append(admin_group)

    admin_user = UserModel(id=_generate_id(), email="admin@example.com", _hashed_password="hashed_pass", is_active=True,
                           group_id=admin_group.id)
    admin_user.group = admin_group
    _mock_users.append(admin_user)

    app.dependency_overrides[get_current_user] = lambda: admin_user
    yield client
    app.dependency_overrides.pop(get_current_user)


# --- Тести, адаптовані для моків (без змін) ---

class TestCertificationCRUD:
    """Група тестів для операцій CRUD над сертифікаціями."""

    async def test_create_certification(self, moderator_client: AsyncClient, mock_db: AsyncSession):
        """Тест створення нової сертифікації модератором."""
        cert_data = {"name": "PG-13"}

        mock_db.execute.side_effect = [
            create_mock_result(None)  # Для перевірки на дублікат
        ]

        response = await moderator_client.post("/api/movies/certifications", json=cert_data)

        assert response.status_code == 201
        assert response.json()["name"] == "PG-13"
        assert "id" in response.json()

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert any(c.name == "PG-13" for c in _mock_certifications)

    async def test_create_certification_duplicate(self, moderator_client: AsyncClient, mock_db: AsyncSession):
        """Тест створення сертифікації з дублікатом імені."""
        cert_data = {"name": "PG-13"}

        existing_cert = CertificationModel(id=_generate_id(), name="PG-13")
        _mock_certifications.append(existing_cert)

        mock_db.execute.side_effect = [
            create_mock_result(existing_cert)  # Для перевірки на дублікат
        ]

        response = await moderator_client.post("/api/movies/certifications", json=cert_data)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

        mock_db.add.assert_not_called()
        mock_db.commit.assert_not_called()
        mock_db.refresh.assert_not_called()
        assert mock_db.execute.called

    async def test_create_certification_unauthorized(self, authenticated_user_client: AsyncClient):
        """Тест створення сертифікації неавторизованим користувачем (звичаний користувач або гість)."""
        cert_data = {"name": "R"}
        response = await authenticated_user_client.post("/api/movies/certifications", json=cert_data)
        assert response.status_code == 403

    async def test_update_certification_moderator(self, moderator_client: AsyncClient, mock_db: AsyncSession):
        """Тест оновлення існуючої сертифікації модератором."""
        existing_cert = CertificationModel(id=_generate_id(), name="Old Cert")
        _mock_certifications.append(existing_cert)

        update_data = {"name": "New Cert"}

        mock_db.execute.side_effect = [
            create_mock_result(existing_cert),  # Для пошуку за ID
            create_mock_result(None)  # Для перевірки дублікатів нового імені
        ]

        response = await moderator_client.put(f"/api/movies/certifications/{existing_cert.id}", json=update_data)

        assert response.status_code == 200
        assert response.json()["name"] == "New Cert"

        updated_in_mock = next((c for c in _mock_certifications if c.id == existing_cert.id), None)
        assert updated_in_mock is not None
        assert updated_in_mock.name == "New Cert"

        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert mock_db.execute.call_count == 2

    async def test_delete_certification_moderator(self, moderator_client: AsyncClient, mock_db: AsyncSession):
        """Тест видалення сертифікації модератором."""
        cert_to_delete = CertificationModel(id=_generate_id(), name="Cert to Delete")
        _mock_certifications.append(cert_to_delete)

        mock_db.execute.side_effect = [
            create_mock_result(cert_to_delete)
        ]

        response = await moderator_client.delete(f"/api/movies/certifications/{cert_to_delete.id}")
        assert response.status_code == 204

        assert not any(c.id == cert_to_delete.id for c in _mock_certifications)
        mock_db.delete.assert_called_once_with(cert_to_delete)
        mock_db.commit.assert_called_once()
        assert mock_db.execute.call_count == 1


class TestGenreCRUD:
    """Група тестів для операцій CRUD над жанрами."""

    async def test_create_genre(self, moderator_client: AsyncClient, mock_db: AsyncSession):
        """Тест створення нового жанру модератором."""
        genre_data = {"name": "Action"}

        mock_db.execute.side_effect = [create_mock_result(None)]  # Жанру з таким іменем ще немає

        response = await moderator_client.post("/api/movies/genres", json=genre_data)

        assert response.status_code == 201
        assert response.json()["name"] == "Action"
        assert "id" in response.json()

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()
        assert any(g.name == "Action" for g in _mock_genres)


class TestMovieCRUD:
    """Група тестів для операцій CRUD над фільмами."""

    async def test_create_movie(self, moderator_client: AsyncClient, mock_db: AsyncSession):
        """Тест створення фільму модератором з усіма залежностями."""
        # Створюємо залежності в мокових сховищах
        cert = CertificationModel(id=_generate_id(), name="PG-13")
        genre_sf = GenreModel(id=_generate_id(), name="Sci-Fi")
        genre_thriller = GenreModel(id=_generate_id(), name="Thriller")
        actor_leo = ActorModel(id=_generate_id(), name="Leonardo DiCaprio")
        actor_joseph = ActorModel(id=_generate_id(), name="Joseph Gordon-Levitt")
        director_nolan = DirectorModel(id=_generate_id(), name="Christopher Nolan")

        _mock_certifications.append(cert)
        _mock_genres.extend([genre_sf, genre_thriller])
        _mock_actors.extend([actor_leo, actor_joseph])
        _mock_directors.append(director_nolan)

        # Налаштування mock_db.execute для пошуку залежностей
        mock_db.execute.side_effect = [
            create_mock_result(cert),  # для certification_id
            create_mock_result(genre_sf),  # для першого genre_id
            create_mock_result(genre_thriller),  # для другого genre_id
            create_mock_result(director_nolan),  # для director_id
            create_mock_result(actor_leo),  # для першого star_id
            create_mock_result(actor_joseph)  # для другого star_id
        ]

        class MovieModelWithMockIds(MovieModel):
            _mock_genre_ids = []
            _mock_director_ids = []
            _mock_actor_ids = []

        # Patch MovieModel in the current test scope to include _mock_ids
        with patch('src.database.models.movies.MovieModel', new=MovieModelWithMockIds):
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
                "certification_id": cert.id,
                "genre_ids": [genre_sf.id, genre_thriller.id],
                "director_ids": [director_nolan.id],
                "star_ids": [actor_leo.id, actor_joseph.id]
            }

            # Перед тим як викликати response, модифікуємо side_effect db.add
            # Щоб mock_refresh міг отримати ці ID
            # Це функція, яка буде викликана при db.add
            async def _mock_add_side_effect_for_movie_creation(instance):
                if isinstance(instance, MovieModelWithMockIds):
                    instance._mock_genre_ids = movie_data["genre_ids"]
                    instance._mock_director_ids = movie_data["director_ids"]
                    instance._mock_actor_ids = movie_data["star_ids"]
                await _single_add_logic(instance)

            mock_db.add.side_effect = _mock_add_side_effect_for_movie_creation

            response = await moderator_client.post("/api/movies", json=movie_data)

            assert response.status_code == 201
            json_response = response.json()
            assert json_response["name"] == "Inception"
            assert json_response["certification"]["name"] == "PG-13"
            assert len(json_response["genres"]) == 2
            assert {g["name"] for g in json_response["genres"]} == {"Sci-Fi", "Thriller"}
            assert len(json_response["directors"]) == 1
            assert {d["name"] for d in json_response["directors"]} == {"Christopher Nolan"}
            assert len(json_response["stars"]) == 2
            assert {a["name"] for a in json_response["stars"]} == {"Leonardo DiCaprio", "Joseph Gordon-Levitt"}

            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()
            assert any(m.name == "Inception" for m in _mock_movies)

            created_movie_mock = next((m for m in _mock_movies if m.name == "Inception"), None)
            assert created_movie_mock is not None
            assert created_movie_mock.certification == cert
            assert genre_sf in created_movie_mock.genres
            assert genre_thriller in created_movie_mock.genres
            assert director_nolan in created_movie_mock.directors
            assert actor_leo in created_movie_mock.actors
            assert actor_joseph in created_movie_mock.actors

    async def test_delete_movie_with_purchase(self, moderator_client: AsyncClient, mock_db: AsyncSession):
        """Тест видалення фільму, який був придбаний (має бути заборонено)."""
        user_model = UserModel(id=_generate_id(), email="buyer@example.com", _hashed_password="hash", is_active=True,
                               group_id=_generate_id())
        user_model.group = UserGroupModel(id=user_model.group_id, name=UserGroupEnum.USER)
        _mock_users.append(user_model)

        cert = CertificationModel(id=_generate_id(), name="PG")
        _mock_certifications.append(cert)

        movie_purchased = MovieModel(
            id=_generate_id(), uuid=uuid4(), name="Purchased Movie", year=2018, time=110, imdb=7.8, votes=1000,
            description="Movie that has been purchased.", price=Decimal("15.00"), certification_id=cert.id
        )
        _mock_movies.append(movie_purchased)

        order = Order(
            id=_generate_id(), user_id=user_model.id, created_at=datetime.utcnow(),
            status=OrderStatusEnum.COMPLETED, total_amount=Decimal("15.00")
        )
        _mock_orders.append(order)

        order_item = OrderItem(
            id=_generate_id(), order_id=order.id, movie_id=movie_purchased.id, price_at_order=Decimal("15.00")
        )
        _mock_order_items.append(order_item)

        mock_db.execute.side_effect = [
            create_mock_result(movie_purchased),  # Для пошуку фільму
            create_mock_result([order_item])  # Для перевірки наявності OrderItem
        ]

        response = await moderator_client.delete(f"/api/movies/{movie_purchased.id}")
        assert response.status_code == 400
        assert "Cannot delete movie: at least one user has purchased it." in response.json()["detail"]

        assert any(m.id == movie_purchased.id for m in _mock_movies)
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()
        assert mock_db.execute.call_count == 2
