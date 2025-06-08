from decimal import Decimal
from typing import cast
from pydantic import HttpUrl

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from config.dependencies import get_jwt_auth_manager
from config.dependencies import get_db
from database.models.accounts import UserModel, UserGroupModel, UserGroupEnum
from database.models.carts import CartModel, CartItemModel
from database.models.movies import MovieModel
from database.models.orders import Order, OrderItem, OrderStatusEnum
from schemas.orders import OrderResponseSchema, OrderItemSchema
from security.http import get_token
from security.interfaces import JWTAuthManagerInterface
from services.payments_services import create_checkout_session_service

#I just assume these will exist in the future. In case they won't, i'll rewrite the routes

router = APIRouter()


@router.post(
    "/users/{user_id}/orders/",
    response_model=OrderResponseSchema,
    status_code=status.HTTP_201_CREATED
)
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

    if user_id != token_user_id:
        stmt = (
            select(UserGroupModel)
            .join(UserModel)
            .where(UserModel.id == token_user_id)
        )
        result = await db.execute(stmt)
        group = result.scalars().first()
        if not group or group.name == UserGroupEnum.USER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    stmt = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")

    stmt_cart = select(CartModel).where(CartModel.user_id == user_id)
    result = await db.execute(stmt_cart)
    cart = result.scalars().first()
    if not cart:
        raise HTTPException(status_code=400, detail="Cart is empty")

    stmt_items = select(CartItemModel).where(CartItemModel.cart_id == cart.id)
    result = await db.execute(stmt_items)
    cart_items = result.scalars().all()
    if not cart_items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    movie_ids = [item.movie_id for item in cart_items]
    if not movie_ids:
        raise HTTPException(status_code=400, detail="No movies in cart")

    stmt_movies = select(MovieModel).where(MovieModel.id.in_(movie_ids), MovieModel.is_available == True)
    result = await db.execute(stmt_movies)
    movies = result.scalars().all()
    if not movies:
        raise HTTPException(status_code=400, detail="No available movies found")

    available_movie_ids = [m.id for m in movies]

    stmt_paid = select(OrderItem.movie_id).join(Order).where(
        and_(
            Order.user_id == user_id,
            Order.status == OrderStatusEnum.COMPLETED,
            OrderItem.movie_id.in_(available_movie_ids)
        )
    )
    result = await db.execute(stmt_paid)
    purchased_movie_ids = {row for row, in result.all()}

    stmt_pending = select(OrderItem.movie_id).join(Order).where(
        and_(
            Order.user_id == user_id,
            Order.status == OrderStatusEnum.PENDING,
            OrderItem.movie_id.in_(available_movie_ids)
        )
    )
    result = await db.execute(stmt_pending)
    pending_movie_ids = {row for row, in result.all()}

    filtered_movies = [m for m in movies if m.id not in purchased_movie_ids and m.id not in pending_movie_ids]
    if not filtered_movies:
        raise HTTPException(status_code=400, detail="All movies already purchased or pending")

    total = sum(m.price for m in filtered_movies)
    order = Order(user_id=user.id, status=OrderStatusEnum.PENDING, total_amount=Decimal(total))
    db.add(order)
    await db.flush()

    items = [OrderItem(order_id=order.id, movie_id=m.id, price_at_order=m.price) for m in filtered_movies]
    db.add_all(items)
    await db.commit()
    await db.refresh(order)

    #creates checkout session
    checkout_link = create_checkout_session_service(order, user)

    return OrderResponseSchema(
        id=order.id,
        created_at=order.created_at,
        status=order.status,
        total_amount=order.total_amount,
        items=[
            OrderItemSchema(
                movie_id=item.movie_id,
                price_at_order=item.price_at_order
            ) for item in items
        ],
        payment_url=cast(HttpUrl, checkout_link.url),
    )

