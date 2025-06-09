from decimal import Decimal
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models.cart import CartItemModel, CartModel
from src.database.models.movies import MovieModel
from src.database.models.orders import Order, OrderItem, OrderStatusEnum
from src.exceptions.cart import CartNotFoundError, MovieAlreadyInCartError, MovieNotInCartError
from src.schemas.cart import CartItemResponseSchema, CartResponseSchema, CartValidationResponseSchema, MovieInCartSchema


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
    async def get_cart_with_movie_details(user_id: int, session: AsyncSession) -> Optional[CartResponseSchema]:
        """Get user's cart with all movie details and purchase status"""
        cart = await CartService.get_cart_with_items(user_id, session)
        if not cart:
            return None

        # Get movie IDs from cart
        movie_ids = [item.movie_id for item in cart.cart_items]
        if not movie_ids:
            return CartResponseSchema(
                id=cart.id,
                user_id=cart.user_id,
                created_at=cart.created_at,
                cart_items=[],
                total_price=Decimal("0.00"),
                total_items=0,
                available_items=0,
            )

        # Get movie details
        movies_query = select(MovieModel).options(selectinload(MovieModel.genres)).where(MovieModel.id.in_(movie_ids))
        movies_result = await session.execute(movies_query)
        movies = {movie.id: movie for movie in movies_result.scalars().all()}

        # Get purchased movie IDs for this user
        purchased_movie_ids = await CartService._get_purchased_movie_ids(user_id, session)

        # Build cart items with movie details
        cart_items = []
        total_price = Decimal("0.00")
        available_items = 0

        for cart_item in cart.cart_items:
            movie = movies.get(cart_item.movie_id)
            is_purchased = cart_item.movie_id in purchased_movie_ids

            movie_schema = None
            if movie:
                movie_schema = MovieInCartSchema(
                    id=movie.id,
                    name=movie.name,
                    year=movie.year,
                    price=movie.price,
                    genres=[genre.name for genre in movie.genres],
                )

                if not is_purchased:
                    total_price += Decimal(str(movie.price))
                    available_items += 1

            cart_item_schema = CartItemResponseSchema(
                id=cart_item.id,
                cart_id=cart_item.cart_id,
                movie_id=cart_item.movie_id,
                added_at=cart_item.added_at,
                movie=movie_schema,
                is_purchased=is_purchased,
            )
            cart_items.append(cart_item_schema)

        return CartResponseSchema(
            id=cart.id,
            user_id=cart.user_id,
            created_at=cart.created_at,
            cart_items=cart_items,
            total_price=total_price,
            total_items=len(cart_items),
            available_items=available_items,
        )

    @staticmethod
    async def _get_purchased_movie_ids(user_id: int, session: AsyncSession) -> set[int]:
        """Get set of movie IDs that user has already purchased"""
        query = (
            select(OrderItem.movie_id)
            .join(Order)
            .where(and_(Order.user_id == user_id, Order.status == OrderStatusEnum.COMPLETED))
        )
        result = await session.execute(query)
        return {movie_id for movie_id, in result.all()}

    @staticmethod
    async def add_movie_to_cart(user_id: int, movie_id: int, session: AsyncSession) -> CartItemModel:
        """
        Add a movie to user's cart.
        Validates that:
        - Movie exists
        - Movie is not already in cart
        - Movie has not been purchased
        """
        # Check if movie exists
        movie_query = select(MovieModel).where(MovieModel.id == movie_id)
        movie_result = await session.execute(movie_query)
        movie = movie_result.scalar_one_or_none()

        if not movie:
            from src.exceptions.cart import MovieNotFoundError

            raise MovieNotFoundError()

        # Check if movie has already been purchased
        purchased_movie_ids = await CartService._get_purchased_movie_ids(user_id, session)
        if movie_id in purchased_movie_ids:
            from src.exceptions.cart import MovieAlreadyPurchasedError

            raise MovieAlreadyPurchasedError()

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

        # Add movie to cart
        cart_item = CartItemModel(cart_id=cart.id, movie_id=movie_id)
        session.add(cart_item)
        await session.flush()

        # Load cart_item with movie and its genres
        from sqlalchemy.orm import selectinload

        query = (
            select(CartItemModel)
            .options(selectinload(CartItemModel.movie).selectinload(MovieModel.genres))
            .where(CartItemModel.id == cart_item.id)
        )
        result = await session.execute(query)
        cart_item = result.scalar_one()

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
    async def validate_cart_for_purchase(user_id: int, session: AsyncSession) -> CartValidationResponseSchema:
        """
        Validate cart items for purchase.
        Returns detailed validation information about cart items.
        """
        cart = await CartService.get_cart_with_items(user_id, session)

        if not cart:
            raise CartNotFoundError()

        movie_ids = [item.movie_id for item in cart.cart_items]
        if not movie_ids:
            return CartValidationResponseSchema(
                available_movies=[],
                purchased_movies=[],
                unavailable_movies=[],
                total_price=Decimal("0.00"),
                message="Cart is empty",
            )

        # Get existing movies
        movies_query = select(MovieModel).where(MovieModel.id.in_(movie_ids))
        movies_result = await session.execute(movies_query)
        existing_movies = {movie.id: movie for movie in movies_result.scalars().all()}

        # Get purchased movie IDs
        purchased_movie_ids = await CartService._get_purchased_movie_ids(user_id, session)

        # Categorize movies
        available_movies = []
        purchased_movies = []
        unavailable_movies = []
        total_price = Decimal("0.00")

        for movie_id in movie_ids:
            if movie_id in purchased_movie_ids:
                purchased_movies.append(movie_id)
            elif movie_id in existing_movies:
                available_movies.append(movie_id)
                total_price += Decimal(str(existing_movies[movie_id].price))
            else:
                unavailable_movies.append(movie_id)

        # Generate message
        message_parts = []
        if available_movies:
            message_parts.append(f"{len(available_movies)} items available for purchase")
        if purchased_movies:
            message_parts.append(f"{len(purchased_movies)} items already purchased")
        if unavailable_movies:
            message_parts.append(f"{len(unavailable_movies)} items unavailable")

        message = "; ".join(message_parts) if message_parts else "Cart is empty"

        return CartValidationResponseSchema(
            available_movies=available_movies,
            purchased_movies=purchased_movies,
            unavailable_movies=unavailable_movies,
            total_price=total_price,
            message=message,
        )
