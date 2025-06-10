from decimal import Decimal
from fastapi  import HTTPException
from sqlalchemy.orm import selectinload
import stripe
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import UserModel, CartModel, CartItemModel
from src.database.models.orders import Order, OrderStatusEnum
from src.database.models.payments import PaymentsModel, PaymentStatus, PaymentsItemModel


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
    stmt = (
        select(PaymentsModel)
        .options(selectinload(PaymentsModel.order))
        .where(PaymentsModel.external_payment_id == stripe_payment_intent)
    )
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()

    if payment:
        payment.status = PaymentStatus.REFUNDED

        if payment.order:
            payment.order.status = OrderStatusEnum.CANCELED

        await db.commit()


async def get_order_for_user(order_id: int, user: UserModel, db: AsyncSession) -> Order | None:
    stmt = select(Order).where(Order.id == order_id, Order.user_id == user.id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def clear_user_cart(user_id: int, db: AsyncSession):
    stmt = delete(CartItemModel).where(CartItemModel.cart_id.in_(
        select(CartModel.id).where(CartModel.user_id == user_id)
    ))
    await db.execute(stmt)
    await db.commit()


async def create_payment_in_db(
    user_id: int,
    order_id: int,
    amount: Decimal,
    stripe_id: str,
    status: str,
    db: AsyncSession,
):
    await clear_user_cart(user_id, db)

    stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id)
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    expected_amount = sum(item.price_at_order for item in order.items)
    if Decimal(str(amount)).quantize(Decimal("0.01")) != expected_amount.quantize(Decimal("0.01")):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid payment amount. Expected {expected_amount}, got {amount}"
        )

    match status:
        case "paid":
            payment_status = PaymentStatus.SUCCESSFUL
        case "unpaid":
            payment_status = PaymentStatus.CANCELED
        case "pending":
            payment_status = PaymentStatus.PENDING
        case _:
            payment_status = PaymentStatus.PENDING  # Default to pending for unknown statuses

    payment = PaymentsModel(
        user_id=user_id,
        order_id=order_id,
        amount=amount,
        status=payment_status,
        external_payment_id=stripe_id,
    )
    db.add(payment)
    await db.flush()

    # Only create payment items and mark order as completed for successful payments
    if payment_status == PaymentStatus.SUCCESSFUL:
        for item in order.items:
            db.add(PaymentsItemModel(
                payment_id=payment.id,
                order_item_id=item.id,
                price_at_payment=item.price_at_order
            ))
        
        # Mark order as completed
        order.status = OrderStatusEnum.COMPLETED
    
    await db.commit()


def create_checkout_session_service(order: Order, user: UserModel):
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    line_items = [
        {
            "price_data": {
                "currency": "USD",
                "product_data": {"name": f"Movie #{item.movie_id}"},  # TODO: use movie name if available
                "unit_amount": int(item.price_at_order * 100),
            },
            "quantity": 1,
        }
        for item in order.items
    ]

    base_url = "http://domen.com/api"
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