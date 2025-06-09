import logging
import os
from typing import Optional
from datetime import date
import stripe
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.requests import Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from src.tasks import send_email_notification

from src.database.models.accounts import UserModel
from src.config.dependencies import get_current_user, get_db
from src.database.models.payments import PaymentsModel, PaymentsModel
from src.schemas.payments import PaymentListResponseSchema, PaymentDetailResponseSchema
from src.services.payments_services import get_order_for_user, create_checkout_session_service, create_payment_in_db

from src.services.payments_services import clear_user_cart

router = APIRouter()

stripe.api_key = os.environ.get["STRIPE_API_KEY"]

@router.post("/create-checkout-session/")
async def create_checkout_session(
        order_id: int,
        db: AsyncSession = Depends(get_db),
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
):
    try:
        payload = jwt_manager.decode_access_token(token)
        token_user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    order = await get_order_for_user(order_id, token_user_id, db)  # async якщо треба
    return create_checkout_session_service(order, user)


@router.post("/stripe/webhook/")
async def stripe_webhook(request: Request):
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
        user_id = session["metadata"]["user_id"]
        order_id = session["metadata"]["order_id"]

        await create_payment_in_db(
            order_id=order_id,
            user_id=user_id,
            amount=session["data"]["amount"],
            stripe_id=session["id"],
            status=session["payment_status"]
        )
        send_email_notification.delay(
            user_id=user_id,
            subject="Your Payment Was Successful",
            template_name="payment_success.html"
        )

# @router.get("/payments/history")
# def get_payments_history(
#         user: UserModel = Depends(get_current_user),
#         db: AsyncSession = Depends(get_db)
# ) -> PaymentsListResponseSchema:
#     return db.query(Payments).filter_by(Payments.user_id=user.id).all()

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
    user_role = user.group.name
    is_moderator = user_role == "moderator" or user_role == "admin"

    stmt = select(PaymentsModel)
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
        if user_id is not None:
            stmt = stmt.where(PaymentsModel.user_id == user_id)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    if not total_items:
        raise HTTPException(status_code=404, detail="No payments found.")

    order_by = PaymentsModel.default_order_by()
    if order_by:
        stmt = stmt.order_by(*order_by)

    stmt = stmt.offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    payments = result.scalars().all()

    payments_list = [PaymentDetailResponseSchema.model_validate(payment) for payment in payments]

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
