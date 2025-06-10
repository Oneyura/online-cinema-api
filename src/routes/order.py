from datetime import datetime
from decimal import Decimal
from typing import List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import HttpUrl
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config.dependencies import get_db, get_jwt_auth_manager, get_current_user
from src.database.models.accounts import UserGroupEnum, UserGroupModel, UserModel
from src.database.models.cart import CartItemModel, CartModel
from src.database.models.movies import MovieModel
from src.database.models.orders import Order, OrderItem, OrderStatusEnum
from src.schemas.orders import OrderItemSchema, OrderResponseSchema
from src.security.http import get_token
from src.security.interfaces import JWTAuthManagerInterface
from src.services.payments_services import create_checkout_session_service

router = APIRouter()


@router.post("/users/{user_id}/orders/", response_model=OrderResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_order(
    user_id: int,
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
) -> OrderResponseSchema:
    try:
        payload = jwt_manager.decode_access_token(token)
        token_user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if user_id != token_user_id:
        stmt = select(UserGroupModel).join(UserModel).where(UserModel.id == token_user_id)
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

    stmt_movies = select(MovieModel).where(MovieModel.id.in_(movie_ids))
    result = await db.execute(stmt_movies)
    movies = result.scalars().all()
    if not movies:
        raise HTTPException(status_code=400, detail="No available movies found")

    available_movie_ids = [m.id for m in movies]

    stmt_paid = (
        select(OrderItem.movie_id)
        .join(Order)
        .where(
            and_(
                Order.user_id == user_id,
                Order.status == OrderStatusEnum.COMPLETED,
                OrderItem.movie_id.in_(available_movie_ids),
            )
        )
    )
    result = await db.execute(stmt_paid)
    purchased_movie_ids = {row for row, in result.all()}

    stmt_pending = (
        select(OrderItem.movie_id)
        .join(Order)
        .where(
            and_(
                Order.user_id == user_id,
                Order.status == OrderStatusEnum.PENDING,
                OrderItem.movie_id.in_(available_movie_ids),
            )
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

    # creates checkout session
    checkout_link = create_checkout_session_service(order, user)

    return OrderResponseSchema(
        id=order.id,
        created_at=order.created_at,
        status=order.status,
        total_amount=order.total_amount,
        items=[OrderItemSchema(movie_id=item.movie_id, price_at_order=item.price_at_order) for item in items],
        payment_url=cast(HttpUrl, checkout_link.url),
    )


@router.get("/users/{user_id}/orders/", response_model=List[OrderResponseSchema])
async def get_user_orders(
    user_id: int,
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
):
    payload = jwt_manager.decode_access_token(token)
    token_user_id = payload.get("user_id")

    if user_id != token_user_id:
        raise HTTPException(status_code=403, detail="Access forbidden")

    stmt = select(Order).where(Order.user_id == user_id)
    result = await db.execute(stmt)
    orders = result.scalars().all()

    response = []
    for order in orders:
        order_items = [
            OrderItemSchema(movie_id=item.movie_id, price_at_order=item.price_at_order) for item in order.items
        ]
        response.append(
            OrderResponseSchema(
                id=order.id,
                created_at=order.created_at,
                status=order.status,
                total_amount=order.total_amount,
                items=order_items,
                payment_url=None,
            )
        )

    return response


@router.get("/admin/orders/", response_model=List[OrderResponseSchema])
async def get_all_orders_admin(
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
    user_id: Optional[int] = None,
    status_filter: Optional[OrderStatusEnum] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
):
    payload = jwt_manager.decode_access_token(token)
    token_user_id = payload.get("user_id")

    stmt = select(UserGroupModel).join(UserModel).where(UserModel.id == token_user_id)
    result = await db.execute(stmt)
    group = result.scalars().first()
    if not group or group.name != UserGroupEnum.ADMIN:
        raise HTTPException(status_code=403, detail="Admins only")

    stmt = select(Order)
    conditions = []

    if user_id:
        conditions.append(Order.user_id == user_id)
    if status_filter:
        conditions.append(Order.status == status_filter)
    if date_from:
        conditions.append(Order.created_at >= date_from)
    if date_to:
        conditions.append(Order.created_at <= date_to)

    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await db.execute(stmt)
    orders = result.scalars().all()

    response = []
    for order in orders:
        order_items = [
            OrderItemSchema(movie_id=item.movie_id, price_at_order=item.price_at_order) for item in order.items
        ]
        response.append(
            OrderResponseSchema(
                id=order.id,
                created_at=order.created_at,
                status=order.status,
                total_amount=order.total_amount,
                items=order_items,
                payment_url=None,
            )
        )

    return response


@router.delete("/orders/{order_id}/")
async def cancel_order(
    order_id: int,
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
    db: AsyncSession = Depends(get_db),
):
    payload = jwt_manager.decode_access_token(token)
    token_user_id = payload.get("user_id")

    stmt = select(Order).where(Order.id == order_id)
    result = await db.execute(stmt)
    order = result.scalars().first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.user_id != token_user_id:
        raise HTTPException(status_code=403, detail="Access forbidden")

    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(status_code=400, detail="Only pending orders can be canceled")

    order.status = OrderStatusEnum.CANCELED
    await db.commit()

    return {"detail": "Order canceled"}


@router.post("/orders/create", status_code=status.HTTP_201_CREATED)
async def create_order_simple(
    use_cart: bool = True,
    movie_ids: Optional[List[int]] = None,
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Simple order creation endpoint that uses current user authentication"""
    
    if use_cart:
        # Get items from cart
        stmt_cart = select(CartModel).where(CartModel.user_id == user.id)
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
        raise HTTPException(status_code=400, detail="No movies specified")

    # Get movies
    stmt_movies = select(MovieModel).where(MovieModel.id.in_(movie_ids))
    result = await db.execute(stmt_movies)
    movies = result.scalars().all()
    if not movies:
        raise HTTPException(status_code=400, detail="No available movies found")

    available_movie_ids = [m.id for m in movies]

    # Check for already purchased movies
    stmt_paid = (
        select(OrderItem.movie_id)
        .join(Order)
        .where(
            and_(
                Order.user_id == user.id,
                Order.status == OrderStatusEnum.COMPLETED,
                OrderItem.movie_id.in_(available_movie_ids),
            )
        )
    )
    result = await db.execute(stmt_paid)
    purchased_movie_ids = {row for row, in result.all()}

    # Check for pending orders
    stmt_pending = (
        select(OrderItem.movie_id)
        .join(Order)
        .where(
            and_(
                Order.user_id == user.id,
                Order.status == OrderStatusEnum.PENDING,
                OrderItem.movie_id.in_(available_movie_ids),
            )
        )
    )
    result = await db.execute(stmt_pending)
    pending_movie_ids = {row for row, in result.all()}

    filtered_movies = [m for m in movies if m.id not in purchased_movie_ids and m.id not in pending_movie_ids]
    if not filtered_movies:
        raise HTTPException(status_code=400, detail="All movies already purchased or pending")

    # Create order
    total = sum(m.price for m in filtered_movies)
    order = Order(user_id=user.id, status=OrderStatusEnum.PENDING, total_amount=Decimal(total))
    db.add(order)
    await db.flush()

    # Create order items
    items = [OrderItem(order_id=order.id, movie_id=m.id, price_at_order=m.price) for m in filtered_movies]
    db.add_all(items)
    await db.commit()
    await db.refresh(order)

    return {
        "id": order.id,
        "status": order.status.value,
        "total_amount": float(order.total_amount),
        "created_at": order.created_at,
        "item_count": len(items)
    }


@router.get("/orders/", response_model=List[OrderResponseSchema])
async def get_current_user_orders(
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get orders for current authenticated user"""
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    )
    result = await db.execute(stmt)
    orders = result.scalars().all()

    if not orders:
        raise HTTPException(status_code=404, detail="No orders found")

    response = []
    for order in orders:
        order_items = [
            OrderItemSchema(movie_id=item.movie_id, price_at_order=item.price_at_order) 
            for item in order.items
        ]
        response.append(
            OrderResponseSchema(
                id=order.id,
                created_at=order.created_at,
                status=order.status,
                total_amount=order.total_amount,
                items=order_items,
                payment_url=None,
            )
        )

    return response


@router.get("/orders/simple")
async def get_current_user_orders_simple(
    user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get orders for current authenticated user - simple version"""
    stmt = (
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
    )
    result = await db.execute(stmt)
    orders = result.scalars().all()

    if not orders:
        return {"orders": [], "message": "No orders found"}

    orders_data = []
    for order in orders:
        order_data = {
            "id": order.id,
            "created_at": order.created_at.isoformat(),
            "status": order.status.value,
            "total_amount": float(order.total_amount),
            "items": [
                {
                    "movie_id": item.movie_id,
                    "price_at_order": float(item.price_at_order)
                }
                for item in order.items
            ]
        }
        orders_data.append(order_data)

    return {"orders": orders_data, "count": len(orders_data)}
