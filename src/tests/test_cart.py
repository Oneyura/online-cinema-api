import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models.cart import CartModel, CartItemModel
from src.services.cart_service import CartService
from src.exceptions.cart import (
    MovieAlreadyInCartError,
    CartNotFoundError,
)


class TestCartModel:
    """Test CartModel functionality"""

    def test_cart_creation(self):
        """Test cart model creation"""
        cart = CartModel(user_id=1)
        assert cart.user_id == 1
        assert cart.id is None  # Not set until saved

    def test_cart_model_repr(self):
        """Test cart model string representation"""
        cart = CartModel(user_id=1)
        repr_str = repr(cart)
        assert "CartModel" in repr_str
        assert "user_id=1" in repr_str

    def test_cart_relationship(self):
        """Test cart-items relationship"""
        cart = CartModel(user_id=1)
        cart_item = CartItemModel(movie_id=1)
        cart.cart_items = [cart_item]
        assert len(cart.cart_items) == 1
        assert cart.cart_items[0].movie_id == 1


class TestCartItemModel:
    """Test CartItemModel functionality"""

    def test_cart_item_model_creation(self):
        """Test cart item model creation"""
        cart_item = CartItemModel(cart_id=1, movie_id=1)
        assert cart_item.cart_id == 1
        assert cart_item.movie_id == 1
        assert cart_item.id is None  # Not set until saved

    def test_cart_item_model_repr(self):
        """Test cart item model string representation"""
        cart_item = CartItemModel(cart_id=1, movie_id=1)
        repr_str = repr(cart_item)
        assert "CartItemModel" in repr_str
        assert "cart_id=1" in repr_str
        assert "movie_id=1" in repr_str

    def test_cart_item_with_timestamp(self):
        """Test cart item with timestamp"""
        now = datetime.now()
        cart_item = CartItemModel(cart_id=1, movie_id=1, added_at=now)
        assert cart_item.added_at == now


class TestCartSchemas:
    """Test cart schemas"""

    def test_cart_item_add_schema(self):
        """Test CartItemAddSchema validation"""
        from src.schemas.cart import CartItemAddSchema

        # Valid data
        schema = CartItemAddSchema(movie_id=1)
        assert schema.movie_id == 1

        # Invalid data - zero movie_id should fail
        with pytest.raises(ValueError):
            CartItemAddSchema(movie_id=0)

    def test_cart_item_remove_schema(self):
        """Test CartItemRemoveSchema validation"""
        from src.schemas.cart import CartItemRemoveSchema

        # Valid data
        schema = CartItemRemoveSchema(movie_id=1)
        assert schema.movie_id == 1

        # Invalid data - zero movie_id should fail
        with pytest.raises(ValueError):
            CartItemRemoveSchema(movie_id=0)


class TestCartService:
    """Test CartService functionality"""

    @pytest.fixture
    def mock_session(self):
        """Create a mock async session"""
        return AsyncMock(spec=AsyncSession)

    @pytest.mark.asyncio
    async def test_add_movie_to_cart_already_exists(self, mock_session):
        """Test adding movie that's already in cart"""
        with patch.object(CartService, "get_or_create_cart") as mock_get_cart:

            # Mock cart and existing item
            cart = CartModel(id=1, user_id=1, created_at=datetime.now())
            existing_item = CartItemModel(id=1, cart_id=1, movie_id=1, added_at=datetime.now())

            # Mock get_or_create_cart as an async function
            async def mock_get_or_create(user_id, session):
                return cart

            mock_get_cart.side_effect = mock_get_or_create

            # Mock existing cart item found
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = existing_item
            mock_session.execute.return_value = mock_result

            with pytest.raises(MovieAlreadyInCartError):
                await CartService.add_movie_to_cart(1, 1, mock_session)

    @pytest.mark.asyncio
    async def test_remove_movie_from_cart_success(self, mock_session):
        """Test successfully removing movie from cart"""
        with patch.object(CartService, "get_cart_with_items") as mock_get_cart:

            # Mock cart with items
            cart_item = CartItemModel(id=1, cart_id=1, movie_id=1, added_at=datetime.now())
            cart = CartModel(id=1, user_id=1, created_at=datetime.now())
            cart.cart_items = [cart_item]

            # Mock get_cart_with_items as an async function
            async def mock_get_cart_func(user_id, session):
                return cart

            mock_get_cart.side_effect = mock_get_cart_func

            # Mock finding cart item to remove
            mock_result = AsyncMock()
            mock_result.scalar_one_or_none.return_value = cart_item
            mock_session.execute.return_value = mock_result

            await CartService.remove_movie_from_cart(1, 1, mock_session)

            mock_session.delete.assert_called_once()
            mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_movie_cart_not_found(self, mock_session):
        """Test removing movie when cart doesn't exist"""
        with patch.object(CartService, "get_cart_with_items") as mock_get_cart:
            # Mock no cart found
            async def mock_get_cart_func(user_id, session):
                return None

            mock_get_cart.side_effect = mock_get_cart_func

            with pytest.raises(CartNotFoundError):
                await CartService.remove_movie_from_cart(1, 1, mock_session)

    @pytest.mark.asyncio
    async def test_clear_cart_success(self, mock_session):
        """Test successfully clearing cart"""
        with patch.object(CartService, "get_cart_with_items") as mock_get_cart:
            # Mock cart with items
            cart_item1 = CartItemModel(id=1, cart_id=1, movie_id=1, added_at=datetime.now())
            cart_item2 = CartItemModel(id=2, cart_id=1, movie_id=2, added_at=datetime.now())
            cart = CartModel(id=1, user_id=1, created_at=datetime.now())
            cart.cart_items = [cart_item1, cart_item2]

            # Mock get_cart_with_items as an async function
            async def mock_get_cart_func(user_id, session):
                return cart

            mock_get_cart.side_effect = mock_get_cart_func

            await CartService.clear_cart(1, mock_session)

            # Should delete both items
            assert mock_session.delete.call_count == 2
            mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_clear_cart_not_found(self, mock_session):
        """Test clearing cart when cart doesn't exist"""
        with patch.object(CartService, "get_cart_with_items") as mock_get_cart:
            # Mock no cart found
            async def mock_get_cart_func(user_id, session):
                return None

            mock_get_cart.side_effect = mock_get_cart_func

            with pytest.raises(CartNotFoundError):
                await CartService.clear_cart(1, mock_session)

    @pytest.mark.asyncio
    async def test_get_cart_items_count(self, mock_session):
        """Test getting cart items count"""
        with patch.object(CartService, "get_cart_with_items") as mock_get_cart:
            # Mock cart with items
            cart_item1 = CartItemModel(id=1, cart_id=1, movie_id=1, added_at=datetime.now())
            cart_item2 = CartItemModel(id=2, cart_id=1, movie_id=2, added_at=datetime.now())
            cart = CartModel(id=1, user_id=1, created_at=datetime.now())
            cart.cart_items = [cart_item1, cart_item2]

            # Mock get_cart_with_items as an async function
            async def mock_get_cart_func(user_id, session):
                return cart

            mock_get_cart.side_effect = mock_get_cart_func

            count = await CartService.get_cart_items_count(1, mock_session)

            assert count == 2

    @pytest.mark.asyncio
    async def test_get_cart_items_count_no_cart(self, mock_session):
        """Test getting cart items count when no cart exists"""
        with patch.object(CartService, "get_cart_with_items") as mock_get_cart:
            # Mock no cart found
            async def mock_get_cart_func(user_id, session):
                return None

            mock_get_cart.side_effect = mock_get_cart_func

            count = await CartService.get_cart_items_count(1, mock_session)

            assert count == 0


class TestCartIntegration:
    """Integration tests for cart functionality"""

    @pytest.mark.skip(reason="Requires database setup")
    async def test_cart_full_workflow(self):
        """Integration test for complete cart workflow"""
        pass

    @pytest.mark.skip(reason="Requires database setup")
    async def test_cart_user_relationship(self):
        """Test cart relationship with user model"""
        pass

    @pytest.mark.skip(reason="Requires database setup")
    async def test_cart_item_unique_constraint(self):
        """Test that cart items are unique per cart-movie combination"""
        pass
