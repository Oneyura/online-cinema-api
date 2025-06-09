from http.client import HTTPException

from sqlalchemy.orm import Session

from database.models import UserModel
from database.models.orders import Order
from database.models.payments import Payments, PaymentStatus, PaymentsItem
import stripe


# def get_order_for_user(order_id: int, user_id: int, db: Session) -> Order | None:
#     return db.query(Order).filter(Order.id == order_id, Order.user_id == user_id).first()


def create_payment_in_db(
        user_id: int,
        order_id: int,
        amount: float,
        stripe_id: str,
        status: str,
        db: Session,
):
    match status:
        case "paid":
            payment_status = PaymentStatus.SUCCESSFUL
        case "unpaid":
            payment_status = PaymentStatus.CANCELED
        case _:
            raise ValueError(f"Unknown payment status: {status}")

    payment = Payments(
        user_id=user_id,
        order_id=order_id,
        amount=amount,
        status=payment_status,
        external_payment_id=stripe_id,
    )
    db.add(payment)
    db.flush()

    order = db.query(Order).filter(Order.id == order_id).first()
    for item in order.items:
        db.add(PaymentsItem(
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
                "product_data": {"name": item.name},
                "unit_amount": int(item.price * 100),
            },
            "quantity": item.quantity,
        }
        for item in order.items.all()  # or `order.items`, if not relationship
    ]

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        success_url="https://domen.com/success/",  # TODO: in settings
        cancel_url="https://domen.com/cancel/",
        metadata={
            "user_id": user.id,
            "order_id": order.id,
        },
    )

    return session
