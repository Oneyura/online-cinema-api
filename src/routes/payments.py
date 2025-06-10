import os
from typing import Optional
from datetime import date
import stripe
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.requests import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from src.tasks import send_email_notification

from src.database.models.accounts import UserModel
from src.config.dependencies import get_current_user, get_db
from src.database.models.payments import PaymentsModel, PaymentStatus, PaymentsItemModel
from src.database.models.orders import Order, OrderStatusEnum
from src.schemas.payments import PaymentListResponseSchema, PaymentDetailResponseSchema, PaymentCreateSchema
from src.services.payments_services import get_order_for_user, create_checkout_session_service, create_payment_in_db, \
    mark_payment_as_refunded, create_payment_from_stripe_event

from src.services.payments_services import clear_user_cart

router = APIRouter()

stripe.api_key = os.environ.get("STRIPE_API_KEY")

@router.post("/payments/create")
async def create_payment(
    payment_data: PaymentCreateSchema,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Create a payment for an order"""
    order = await get_order_for_user(payment_data.order_id, user, db)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    checkout_session = create_checkout_session_service(order, user)
    return {
        "payment_url": checkout_session.url,
        "session_id": checkout_session.id,
        "order_id": payment_data.order_id
    }

@router.post("/create-checkout-session/")
async def create_checkout_session(
        order_id: int,
        db: AsyncSession = Depends(get_db),
        user: UserModel = Depends(get_current_user),
):
    order = await get_order_for_user(order_id, user, db)  # async якщо треба
    return create_checkout_session_service(order, user)


@router.post("/stripe/webhook/")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await create_payment_from_stripe_event(session, db)

        send_email_notification.delay(
            user_id=session["metadata"]["user_id"],
            subject="Your Payment Was Successful",
            template_name="payment_success.html"
        )

    elif event["type"] == "charge.refunded":
        charge = event["data"]["object"]
        await mark_payment_as_refunded(charge["payment_intent"], db)

    return {"status": "ok"}

@router.get("/payments/")
async def get_payments(
        page: int = Query(1, ge=1, description="Page number (1-based index)"),
        per_page: int = Query(10, ge=1, le=20, description="Number of items per page"),
        date_from: Optional[date] = Query(None, description="Start date"),
        date_to: Optional[date] = Query(None, description="End date"),
        user_filter: Optional[int] = Query(None, description="Filter by user ID (moderators only)"),
        status: Optional[PaymentStatus] = Query(None, description="Filter by payment status"),
        db: AsyncSession = Depends(get_db),
        user: UserModel = Depends(get_current_user)
) -> PaymentListResponseSchema:
    user_id = user.id
    user_role = user.group.name if user.group else "user"
    is_moderator = user_role in ["moderator", "admin"]

    # Build query with eager loading
    stmt = select(PaymentsModel).options(
        selectinload(PaymentsModel.payment_items)
    )
    
    if is_moderator:
        if user_filter:
            stmt = stmt.where(PaymentsModel.user_id == user_filter)
        if date_from:
            stmt = stmt.where(PaymentsModel.created_at >= date_from)
        if date_to:
            stmt = stmt.where(PaymentsModel.created_at <= date_to)
        if status:
            stmt = stmt.where(PaymentsModel.status == status)
    else:
        stmt = stmt.where(PaymentsModel.user_id == user_id)

    # Count total items
    count_stmt = select(func.count(PaymentsModel.id))
    if not is_moderator:
        count_stmt = count_stmt.where(PaymentsModel.user_id == user_id)
    
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    if not total_items:
        raise HTTPException(status_code=404, detail="No payments found.")

    # Apply ordering and pagination
    stmt = stmt.order_by(PaymentsModel.id.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    payments = result.scalars().all()

    # Convert to response format
    payments_list = []
    for payment in payments:
        payment_dict = {
            "id": payment.id,
            "order_id": payment.order_id,
            "created_at": payment.created_at,
            "status": payment.status.value,
            "amount": float(payment.amount),
            "external_payment_id": payment.external_payment_id,
            "user_id": payment.user_id,
            "payment_items": [
                {
                    "id": item.id,
                    "price_at_payment": float(item.price_at_payment),
                    "order_item_id": item.order_item_id
                }
                for item in payment.payment_items
            ]
        }
        payments_list.append(PaymentDetailResponseSchema.model_validate(payment_dict))

    total_pages = (total_items + per_page - 1) // per_page

    return PaymentListResponseSchema(
        payments=payments_list,
        prev_page=f"/payments/?page={page - 1}&per_page={per_page}" if page > 1 else None,
        next_page=f"/payments/?page={page + 1}&per_page={per_page}" if page < total_pages else None,
        total_pages=total_pages,
        total_items=total_items,
    )

@router.get("/payment/cancel")
async def payment_cancel(order_id: int):
    return {
        "detail": "Payment was cancelled.",
        "message": "You can try again with another payment method.",
        "order_id": order_id,
        "retry_endpoint": "/create-checkout-session/"
    }

@router.post("/payments/create-simple")
async def create_payment_simple(
    payment_data: PaymentCreateSchema,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Create a simple payment without Stripe integration for testing"""
    
    # Get order with items
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == payment_data.order_id, Order.user_id == user.id)
    )
    result = await db.execute(stmt)
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(status_code=400, detail="Order is not pending")
    
    # Create payment with PENDING status
    payment = PaymentsModel(
        user_id=user.id,
        order_id=order.id,
        amount=order.total_amount,
        status=PaymentStatus.PENDING,
        external_payment_id=f"test_payment_{order.id}_{user.id}",
    )
    db.add(payment)
    await db.flush()
    
    # Create payment items
    for item in order.items:
        payment_item = PaymentsItemModel(
            payment_id=payment.id,
            order_item_id=item.id,
            price_at_payment=item.price_at_order
        )
        db.add(payment_item)
    
    await db.commit()
    
    return {
        "payment_id": payment.id,
        "order_id": order.id,
        "amount": float(payment.amount),
        "status": payment.status.value,
        "external_payment_id": payment.external_payment_id,
        "message": "Payment created successfully. Use /payments/complete/{payment_id} to complete it."
    }


@router.post("/payments/complete/{payment_id}")
async def complete_payment_simple(
    payment_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserModel = Depends(get_current_user),
):
    """Complete a payment for testing"""
    
    # Get payment with order
    stmt = (
        select(PaymentsModel)
        .options(selectinload(PaymentsModel.order))
        .where(PaymentsModel.id == payment_id, PaymentsModel.user_id == user.id)
    )
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    if payment.status != PaymentStatus.PENDING:
        raise HTTPException(status_code=400, detail="Payment is not pending")
    
    # Complete payment
    payment.status = PaymentStatus.SUCCESSFUL
    payment.order.status = OrderStatusEnum.COMPLETED
    
    await db.commit()
    
    return {
        "payment_id": payment.id,
        "order_id": payment.order_id,
        "status": payment.status.value,
        "order_status": payment.order.status.value,
        "message": "Payment completed successfully!"
    }
