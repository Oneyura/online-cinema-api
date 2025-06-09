from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import get_async_session
from src.exceptions.cart import (
    BaseCartError,
    CartNotFoundError,
    MovieAlreadyInCartError,
    MovieAlreadyPurchasedError,
    MovieNotFoundError,
    MovieNotInCartError,
)
from src.schemas.cart import (
    CartItemAddSchema,
    CartItemRemoveSchema,
    CartItemResponseSchema,
    CartResponseSchema,
    CartSummarySchema,
)
from src.services.cart_service import CartService

router = APIRouter(prefix="/cart", tags=["cart"])


# TODO: Replace with actual user authentication dependency
async def get_current_user_id() -> int:
    """
    Mock function for getting current user ID.
    Replace with actual authentication dependency when auth is ready.
    """
    return 1  # Mock user ID


@router.get("/", response_model=CartResponseSchema)
async def get_cart(
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Get user's cart with all items"""
    try:
        cart = await CartService.get_cart_with_items(current_user_id, session)

        if not cart:
            # Create empty cart if doesn't exist
            cart = await CartService.get_or_create_cart(current_user_id, session)
            await session.commit()

        return cart

    except BaseCartError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/summary", response_model=CartSummarySchema)
async def get_cart_summary(
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Get cart summary (without detailed items)"""
    try:
        cart = await CartService.get_cart_with_items(current_user_id, session)
        items_count = await CartService.get_cart_items_count(current_user_id, session)

        if not cart:
            cart = await CartService.get_or_create_cart(current_user_id, session)
            await session.commit()
            items_count = 0

        return CartSummarySchema(
            id=cart.id,
            user_id=cart.user_id,
            created_at=cart.created_at,
            items_count=items_count,
        )

    except BaseCartError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/items", response_model=CartItemResponseSchema)
async def add_movie_to_cart(
    data: CartItemAddSchema,
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Add a movie to cart"""
    try:
        cart_item = await CartService.add_movie_to_cart(current_user_id, data.movie_id, session)
        await session.commit()
        return cart_item

    except MovieAlreadyInCartError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except MovieAlreadyPurchasedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except MovieNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BaseCartError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/items")
async def remove_movie_from_cart(
    data: CartItemRemoveSchema,
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Remove a movie from cart"""
    try:
        await CartService.remove_movie_from_cart(current_user_id, data.movie_id, session)
        await session.commit()
        return {"message": "Movie removed from cart successfully"}

    except MovieNotInCartError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CartNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BaseCartError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/clear")
async def clear_cart(
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Clear all items from cart"""
    try:
        await CartService.clear_cart(current_user_id, session)
        await session.commit()
        return {"message": "Cart cleared successfully"}

    except CartNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BaseCartError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate")
async def validate_cart_for_purchase(
    current_user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_async_session),
):
    """Validate cart items for purchase"""
    try:
        available_movies = await CartService.validate_cart_for_purchase(current_user_id, session)
        return {
            "available_movies": available_movies,
            "message": f"Cart contains {len(available_movies)} items available for purchase",
        }

    except CartNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BaseCartError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Moderator endpoints
@router.get("/admin/movie/{movie_id}/users", response_model=List[CartResponseSchema])
async def get_users_with_movie_in_cart(
    movie_id: int,
    # TODO: Add moderator/admin authentication dependency
    session: AsyncSession = Depends(get_async_session),
):
    """
    Admin/Moderator endpoint: Get all users who have a specific movie in their cart.
    Useful for checking before deleting a movie.
    """
    try:
        carts = await CartService.get_all_user_carts_with_movie(movie_id, session)
        return carts

    except BaseCartError as e:
        raise HTTPException(status_code=500, detail=str(e))
