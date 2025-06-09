import logging
import os

import stripe
from fastapi import APIRouter, Depends, HTTPException
from fastapi.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.accounts import UserModel
from src.config.dependencies import get_current_user, get_db
from src.database.models.payments import Payments
from src.services.payments_services import get_order_for_user, create_checkout_session_service, create_payment_in_db

router = APIRouter()

stripe.api_key = os.environ.get["STRIPE_API_KEY"]

@router.post("/create-checkout-session/")
async def create_checkout_session(
        order_id: int,
        db: AsyncSession = Depends(get_db),
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        # user: UserModel = Depends(get_current_user) #TODO rewrite with token func
):
    try:
        payload = jwt_manager.decode_access_token(token)
        token_user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    order = await get_order_for_user(order_id, token_user_id, db)  # async якщо треба
    return create_checkout_session_service(order, user)

async def create_order(
        user_id: int,
        token: str = Depends(get_token),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
        db: AsyncSession = Depends(get_db)
) -> OrderResponseSchema:
    try:
        payload = jwt_manager.decode_access_token(token)
        token_user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

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

# @router.get("/payments/history")
# def get_payments_history(
#         user: UserModel = Depends(get_current_user),
#         db: AsyncSession = Depends(get_db)
# ) -> PaymentsListResponseSchema:
#     return db.query(Payments).filter_by(Payments.user_id=user.id).all()