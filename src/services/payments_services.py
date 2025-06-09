from decimal import Decimal
from http.client import HTTPException

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.database.models import UserModel
from src.database.models.orders import Order
import stripe
from src.database.models.payments import PaymentsModel, PaymentStatus, PaymentsItemModel

from src.database.models import CartItemModel
from src.database.models import PaymentsModel, PaymentStatus, OrderStatusEnum, Order
from sqlalchemy import select

async def create_payment_from_stripe_event(session, db: AsyncSession):
    user_id = int(session["metadata"]["user_id"])
    order_id = int(session["metadata"]["order_id"])
    amount = int(session["amount_total"]) / 100  # cents to dollars
    stripe_id = session["payment_intent"]
    status = session["payment_status"]

    await create_payment_in_db(
        user_id=user_id,
        order_id=order_id,
        amount=amount,
        stripe_id=stripe_id,
        status=status,
        db=db
    )

async def mark_payment_as_refunded(stripe_payment_intent: str, db: AsyncSession):
    stmt = select(PaymentsModel).where(PaymentsModel.external_payment_id == stripe_payment_intent)
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()

    if payment:
        payment.status = PaymentStatus.REFUNDED

        # також скасовуємо замовлення
        order = await db.get(Order, payment.order_id)
        if order:
            order.status = OrderStatusEnum.CANCELED

        await db.commit()


def get_order_for_user(order_id: int, user: UserModel, db: Session) -> Order | None:
    return db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()


def clear_user_cart(user_id: int, db: Session):
    db.query(CartItemModel).filter(CartItemModel.user_id == user_id).delete()
    db.commit()

def create_payment_in_db(
        user_id: int,
        order_id: int,
        amount: Decimal,
        stripe_id: str,
        status: str,
        db: Session,
):
    clear_user_cart(user_id, db) # Clearing user's cart
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    expected_amount = sum(item.price_at_order for item in order.items)
    if round(amount, 2) != round(expected_amount, 2):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid payment amount. Expected {expected_amount}, got {amount}"
        )

    match status:
        case "paid":
            payment_status = PaymentStatus.SUCCESSFUL
        case "unpaid":
            payment_status = PaymentStatus.CANCELED
        case _:
            raise ValueError(f"Unknown payment status: {status}")

    payment = PaymentsModel(
        user_id=user_id,
        order_id=order_id,
        amount=amount,
        status=payment_status,
        external_payment_id=stripe_id,
    )
    db.add(payment)
    db.flush()

    for item in order.items:
        db.add(PaymentsItemModel(
            payment_id=payment.id,
            order_item_id=item.id,
            price_at_payment=item.price
        ))
    db.commit()


def create_checkout_session_service(order: Order, user: UserModel):
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    line_items = [
        {
            "price_data": {
                "currency": "USD",
                "product_data": {"id": item.id}, #todo change to movie name
                "unit_amount": int(item.price * 100),
            },
            "quantity": item.quantity,
        }
        for item in order.items.all()  # or `order.items`, if not relationship
    ]

    base_url = "http://domen.com/api"  # e.g. http://localhost:8000
    success_url = f"{base_url}/payment/success/?order_id={order.id}"
    cancel_url = f"{base_url}/payment/cancel/?order_id={order.id}"

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": user.id,
            "order_id": order.id,
        },
    )

    return session
