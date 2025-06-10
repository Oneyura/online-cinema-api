import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.orders import Order, OrderItem, OrderStatusEnum
from src.database.models.payments import PaymentStatus, PaymentsModel, PaymentsItemModel
from src.services.payments_services import create_payment_from_stripe_event


@pytest.fixture
def mock_db():
    db = AsyncMock(spec=AsyncSession)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.execute = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_create_payment_successfully_creates_payment_and_items(mock_db):
    order = Order(id=1, user_id=1, status=OrderStatusEnum.PENDING)
    order_item = OrderItem(id=1, order_id=1, movie_id=1, price_at_order=Decimal("9.99"))
    order.items = [order_item]

    async def mock_execute(stmt):
        class Result:
            def scalar_one_or_none(self_inner):
                return order
        return Result()

    mock_db.execute.side_effect = mock_execute

    async def mock_flush():
        payment = mock_db.add.call_args[0][0]
        payment.id = 1
        payment.created_at = datetime.utcnow()

    mock_db.flush.side_effect = mock_flush

    stripe_session = {
        "metadata": {"user_id": "1", "order_id": "1"},
        "amount_total": 999,
        "payment_intent": "pi_12345",
        "payment_status": "paid",
    }

    await create_payment_from_stripe_event(stripe_session, mock_db)

    added_models = [call[0][0] for call in mock_db.add.call_args_list]

    payment = next((m for m in added_models if isinstance(m, PaymentsModel)), None)
    item = next((m for m in added_models if isinstance(m, PaymentsItemModel)), None)

    assert payment is not None
    assert payment.status == PaymentStatus.SUCCESSFUL
    assert item is not None
    assert item.price_at_payment == order_item.price_at_order


@pytest.mark.asyncio
async def test_create_payment_with_invalid_amount_raises_error(mock_db):
    order = Order(id=1, user_id=1, status=OrderStatusEnum.PENDING)
    order_item = OrderItem(id=1, order_id=1, movie_id=1, price_at_order=Decimal("19.99"))
    order.items = [order_item]

    async def mock_execute(stmt):
        class Result:
            def scalar_one_or_none(self_inner):
                return order
        return Result()

    mock_db.execute.side_effect = mock_execute

    stripe_session = {
        "metadata": {"user_id": "1", "order_id": "1"},
        "amount_total": 999,  # 9.99$ instead of 19.99$
        "payment_intent": "pi_12345",
        "payment_status": "paid",
    }

    with pytest.raises(Exception) as exc_info:
        await create_payment_from_stripe_event(stripe_session, mock_db)

    assert "Invalid payment amount" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_payment_with_unpaid_status_sets_canceled(mock_db):
    order = Order(id=1, user_id=1, status=OrderStatusEnum.PENDING)
    order_item = OrderItem(id=1, order_id=1, movie_id=1, price_at_order=Decimal("9.99"))
    order.items = [order_item]

    async def mock_execute(stmt):
        class Result:
            def scalar_one_or_none(self_inner):
                return order
        return Result()

    mock_db.execute.side_effect = mock_execute

    async def mock_flush():
        payment = mock_db.add.call_args[0][0]
        payment.id = 1
        payment.created_at = datetime.utcnow()

    mock_db.flush.side_effect = mock_flush

    stripe_session = {
        "metadata": {"user_id": "1", "order_id": "1"},
        "amount_total": 999,
        "payment_intent": "pi_12345",
        "payment_status": "unpaid",
    }

    await create_payment_from_stripe_event(stripe_session, mock_db)

    added_models = [call[0][0] for call in mock_db.add.call_args_list]
    payment = next((m for m in added_models if isinstance(m, PaymentsModel)), None)

    assert payment is not None
    assert payment.status == PaymentStatus.CANCELED