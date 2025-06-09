import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.accounts import UserModel, UserGroupModel, UserGroupEnum
from src.database.models.cart import CartModel, CartItemModel
from src.database.models.movies import MovieModel
from src.database.models.orders import Order, OrderItem, OrderStatusEnum
from src.schemas.orders import OrderResponseSchema, OrderItemSchema


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.add_all = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def mock_jwt_manager():
    manager = MagicMock()
    manager.decode_access_token.return_value = {"user_id": 1}
    return manager


@pytest.fixture
def mock_user():
    return UserModel(id=1, email="test@example.com", is_active=True, group_id=1)


@pytest.fixture
def mock_movie():
    return MovieModel(
        id=1,
        uuid=uuid4(),
        name="Test Movie",
        year=2024,
        time=120,
        imdb=8.5,
        votes=1000,
        meta_score=85.0,
        gross=1000000.0,
        description="A test movie description",
        price=Decimal("9.99"),
        certification_id=1,
    )


@pytest.fixture
def mock_cart():
    return CartModel(id=1, user_id=1)


@pytest.fixture
def mock_cart_item(mock_cart, mock_movie):
    return CartItemModel(id=1, cart_id=mock_cart.id, movie_id=mock_movie.id)


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
    mock_result.all.return_value = value if isinstance(value, list) else [value]
    return mock_result


@pytest.mark.asyncio
async def test_create_order_success(mock_db, mock_jwt_manager, mock_user, mock_movie, mock_cart, mock_cart_item):
    mock_db.execute.side_effect = [
        create_mock_result(mock_user),
        create_mock_result(mock_cart),
        create_mock_result([mock_cart_item]),
        create_mock_result([mock_movie]),
        create_mock_result([]),
        create_mock_result([]),
    ]

    with patch("src.routes.order.create_checkout_session_service") as mock_checkout:
        mock_checkout.return_value = MagicMock(url="http://test-payment-url.com")

        async def mock_flush():
            order_instance = mock_db.add.call_args[0][0]
            order_instance.id = 1
            order_instance.created_at = datetime.utcnow()
            order_instance.status = OrderStatusEnum.PENDING

        mock_db.flush.side_effect = mock_flush

        from src.routes.order import create_order

        response = await create_order(user_id=1, token="valid_token", jwt_manager=mock_jwt_manager, db=mock_db)

        assert isinstance(response, OrderResponseSchema)
        assert response.status == "PENDING"
        assert response.total_amount == mock_movie.price
        assert len(response.items) == 1
        assert response.items[0].movie_id == mock_movie.id
        assert str(response.payment_url) == "http://test-payment-url.com/"


@pytest.mark.asyncio
async def test_create_order_empty_cart(mock_db, mock_jwt_manager, mock_user):
    mock_db.execute.side_effect = [create_mock_result(mock_user), create_mock_result(None)]

    from src.routes.order import create_order

    with pytest.raises(HTTPException) as exc_info:
        await create_order(user_id=1, token="valid_token", jwt_manager=mock_jwt_manager, db=mock_db)

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Cart is empty"


@pytest.mark.asyncio
async def test_get_user_orders_success(mock_db, mock_jwt_manager):
    order = Order(
        id=1, user_id=1, status=OrderStatusEnum.COMPLETED, total_amount=Decimal("19.98"), created_at=datetime.utcnow()
    )
    order_item = OrderItem(id=1, order_id=1, movie_id=1, price_at_order=Decimal("9.99"))
    order.items = [order_item]

    mock_db.execute.return_value = create_mock_result([order])

    from src.routes.order import get_user_orders

    response = await get_user_orders(user_id=1, token="valid_token", jwt_manager=mock_jwt_manager, db=mock_db)

    assert isinstance(response, list)
    assert len(response) == 1
    assert response[0].id == order.id
    assert response[0].status.value == "COMPLETED"
    assert len(response[0].items) == 1
    assert response[0].items[0].movie_id == order_item.movie_id


@pytest.mark.asyncio
async def test_get_all_orders_admin_success(mock_db, mock_jwt_manager):
    admin_group = UserGroupModel(id=1, name=UserGroupEnum.ADMIN)

    order = Order(
        id=1, user_id=1, status=OrderStatusEnum.COMPLETED, total_amount=Decimal("19.98"), created_at=datetime.utcnow()
    )
    order_item = OrderItem(id=1, order_id=1, movie_id=1, price_at_order=Decimal("9.99"))
    order.items = [order_item]

    mock_db.execute.side_effect = [create_mock_result(admin_group), create_mock_result([order])]

    from src.routes.order import get_all_orders_admin

    response = await get_all_orders_admin(token="valid_token", jwt_manager=mock_jwt_manager, db=mock_db)

    assert isinstance(response, list)
    assert len(response) == 1
    assert response[0].id == order.id
    assert response[0].status == "COMPLETED"


@pytest.mark.asyncio
async def test_cancel_order_success(mock_db, mock_jwt_manager):
    order = Order(
        id=1, user_id=1, status=OrderStatusEnum.PENDING, total_amount=Decimal("19.98"), created_at=datetime.utcnow()
    )

    mock_db.execute.return_value = create_mock_result(order)

    from src.routes.order import cancel_order

    response = await cancel_order(order_id=1, token="valid_token", jwt_manager=mock_jwt_manager, db=mock_db)

    assert response == {"detail": "Order canceled"}
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_order_not_found(mock_db, mock_jwt_manager):
    mock_db.execute.return_value = create_mock_result(None)

    from src.routes.order import cancel_order

    with pytest.raises(HTTPException) as exc_info:
        await cancel_order(order_id=999, token="valid_token", jwt_manager=mock_jwt_manager, db=mock_db)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Order not found"
