from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import get_async_session
from src.database.models.accounts import UserModel
from src.config.dependencies import get_current_user
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
    CartValidationResponseSchema,
)
from src.services.cart_service import CartService

router = APIRouter(prefix="/cart", tags=["cart"])


# Authentication is now handled by get_current_user dependency from src.config.dependencies


@router.get("/guest-info")
async def get_guest_cart_info():
    """
    Endpoint for unauthenticated users.
    Returns information about cart functionality and prompts to sign up.
    """
    return {
        "message": "Cart functionality requires user authentication",
        "features": [
            "Add movies to your personal cart",
            "View detailed movie information (title, price, genre, release year)",
            "See which movies you've already purchased",
            "Pay for all movies in your cart at once",
            "Access your purchase history"
        ],
        "action_required": "Please sign up or log in to use cart functionality",
        "auth_endpoints": {
            "sign_up": "/api/accounts/register/",
            "log_in": "/api/accounts/login/",
            "resend_activation": "/api/accounts/resend-activation/",
            "password_reset": "/api/accounts/password-reset/request/"
        }
    }


@router.get("/", response_model=CartResponseSchema)
async def get_cart(
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get user's cart with all items and movie details"""
    try:
        cart = await CartService.get_cart_with_movie_details(current_user.id, session)

        if not cart:
            # Create empty cart if doesn't exist
            empty_cart = await CartService.get_or_create_cart(current_user.id, session)
            await session.commit()
            
            from decimal import Decimal
            cart = CartResponseSchema(
                id=empty_cart.id,
                user_id=empty_cart.user_id,
                created_at=empty_cart.created_at,
                cart_items=[],
                total_price=Decimal('0.00'),
                total_items=0,
                available_items=0
            )

        return cart

    except BaseCartError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/summary", response_model=CartSummarySchema)
async def get_cart_summary(
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get cart summary with pricing and availability info"""
    try:
        cart_details = await CartService.get_cart_with_movie_details(current_user.id, session)

        if not cart_details:
            empty_cart = await CartService.get_or_create_cart(current_user.id, session)
            await session.commit()
            
            from decimal import Decimal
            return CartSummarySchema(
                id=empty_cart.id,
                user_id=empty_cart.user_id,
                created_at=empty_cart.created_at,
                items_count=0,
                available_items_count=0,
                total_price=Decimal('0.00')
            )

        return CartSummarySchema(
            id=cart_details.id,
            user_id=cart_details.user_id,
            created_at=cart_details.created_at,
            items_count=cart_details.total_items,
            available_items_count=cart_details.available_items,
            total_price=cart_details.total_price
        )

    except BaseCartError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/items", response_model=CartItemResponseSchema)
async def add_movie_to_cart(
    data: CartItemAddSchema,
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Add a movie to cart"""
    try:
        cart_item = await CartService.add_movie_to_cart(current_user.id, data.movie_id, session)
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
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Remove a movie from cart"""
    try:
        await CartService.remove_movie_from_cart(current_user.id, data.movie_id, session)
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
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Clear all items from cart"""
    try:
        await CartService.clear_cart(current_user.id, session)
        await session.commit()
        return {"message": "Cart cleared successfully"}

    except CartNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BaseCartError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validate", response_model=CartValidationResponseSchema)
async def validate_cart_for_purchase(
    current_user: UserModel = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Validate cart items for purchase with detailed breakdown"""
    try:
        validation_result = await CartService.validate_cart_for_purchase(current_user.id, session)
        return validation_result

    except CartNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BaseCartError as e:
        raise HTTPException(status_code=500, detail=str(e))


# Moderator endpoints
@router.get("/admin/movie/{movie_id}/users", response_model=List[CartResponseSchema])
async def get_users_with_movie_in_cart(
    movie_id: int,
    current_user: UserModel = Depends(get_current_user),  # Now has admin authentication
    session: AsyncSession = Depends(get_async_session),
):
    """
    Admin/Moderator endpoint: Get all users who have a specific movie in their cart.
    Useful for checking before deleting a movie.
    """
    # Check if user is admin/moderator
    from sqlalchemy import select
    from src.database.models.accounts import UserGroupModel, UserGroupEnum
    
    stmt = select(UserGroupModel).join(UserModel).where(UserModel.id == current_user.id)
    result = await session.execute(stmt)
    group = result.scalars().first()
    
    if not group or group.name not in [UserGroupEnum.ADMIN, UserGroupEnum.MODERATOR]:
        raise HTTPException(status_code=403, detail="Admin or Moderator access required")
    
    try:
        carts = await CartService.get_all_user_carts_with_movie(movie_id, session)
        return carts

    except BaseCartError as e:
        raise HTTPException(status_code=500, detail=str(e))
