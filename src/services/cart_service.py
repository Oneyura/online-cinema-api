from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models.cart import CartItemModel, CartModel
from src.exceptions.cart import CartNotFoundError, MovieAlreadyInCartError, MovieNotInCartError


class CartService:
    """Service for cart operations"""

    @staticmethod
    async def get_or_create_cart(user_id: int, session: AsyncSession) -> CartModel:
        """
        Get user's cart or create one if it doesn't exist.
        Each user has exactly one cart.
        """
        query = select(CartModel).options(selectinload(CartModel.cart_items)).where(CartModel.user_id == user_id)
        result = await session.execute(query)
        cart = result.scalar_one_or_none()

        if not cart:
            cart = CartModel(user_id=user_id)
            session.add(cart)
            await session.flush()
            # Refresh cart with cart_items loaded
            await session.refresh(cart, ["cart_items"])

        return cart

    @staticmethod
    async def get_cart_with_items(user_id: int, session: AsyncSession) -> Optional[CartModel]:
        """Get user's cart with all items loaded"""
        query = select(CartModel).options(selectinload(CartModel.cart_items)).where(CartModel.user_id == user_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def add_movie_to_cart(user_id: int, movie_id: int, session: AsyncSession) -> CartItemModel:
        """
        Add a movie to user's cart.
        Validates that:
        - Movie exists (assumes movies table exists)
        - Movie is not already in cart
        - Movie has not been purchased (assumes orders/payments logic exists)
        """
        # Get or create cart
        cart = await CartService.get_or_create_cart(user_id, session)

        # Check if movie is already in cart
        existing_item_query = select(CartItemModel).where(
            and_(CartItemModel.cart_id == cart.id, CartItemModel.movie_id == movie_id)
        )
        result = await session.execute(existing_item_query)
        existing_item = result.scalar_one_or_none()

        if existing_item:
            raise MovieAlreadyInCartError()

        # TODO: Add validation for movie existence when movies table is ready
        # TODO: Add validation for already purchased movies when orders/payments are ready

        # Add movie to cart
        cart_item = CartItemModel(cart_id=cart.id, movie_id=movie_id)
        session.add(cart_item)
        await session.flush()
        await session.refresh(cart_item)

        return cart_item

    @staticmethod
    async def remove_movie_from_cart(user_id: int, movie_id: int, session: AsyncSession) -> None:
        """Remove a movie from user's cart"""
        cart = await CartService.get_cart_with_items(user_id, session)

        if not cart:
            raise CartNotFoundError()

        # Find and remove the cart item
        cart_item_query = select(CartItemModel).where(
            and_(CartItemModel.cart_id == cart.id, CartItemModel.movie_id == movie_id)
        )
        result = await session.execute(cart_item_query)
        cart_item = result.scalar_one_or_none()

        if not cart_item:
            raise MovieNotInCartError()

        await session.delete(cart_item)
        await session.flush()

    @staticmethod
    async def clear_cart(user_id: int, session: AsyncSession) -> None:
        """Clear all items from user's cart"""
        cart = await CartService.get_cart_with_items(user_id, session)

        if not cart:
            raise CartNotFoundError()

        # Remove all cart items
        for cart_item in cart.cart_items:
            await session.delete(cart_item)

        await session.flush()

    @staticmethod
    async def get_cart_items_count(user_id: int, session: AsyncSession) -> int:
        """Get the number of items in user's cart"""
        cart = await CartService.get_cart_with_items(user_id, session)

        if not cart:
            return 0

        return len(cart.cart_items)

    @staticmethod
    async def get_all_user_carts_with_movie(movie_id: int, session: AsyncSession) -> List[CartModel]:
        """
        Get all carts that contain a specific movie.
        Useful for moderators to check which users have a movie in their cart
        before deleting it.
        """
        query = (
            select(CartModel)
            .join(CartItemModel)
            .options(selectinload(CartModel.cart_items))
            .where(CartItemModel.movie_id == movie_id)
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def validate_cart_for_purchase(user_id: int, session: AsyncSession) -> List[int]:
        """
        Validate cart items for purchase.
        Returns list of movie IDs that are available for purchase.
        TODO: Implement proper validation when orders/payments are ready.
        """
        cart = await CartService.get_cart_with_items(user_id, session)

        if not cart:
            raise CartNotFoundError()

        # For now, return all movie IDs in cart
        # TODO: Add validation for movie availability and already purchased items
        return [item.movie_id for item in cart.cart_items]
