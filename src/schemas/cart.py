from datetime import datetime
from typing import List, Optional
from decimal import Decimal

from pydantic import BaseModel, Field, ConfigDict


class CartItemAddSchema(BaseModel):
    """Schema for adding a movie to cart"""

    movie_id: int = Field(..., description="ID of the movie to add to cart", gt=0)


class MovieInCartSchema(BaseModel):
    """Schema for movie details in cart"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str = Field(..., description="Movie title")
    year: int = Field(..., description="Release year")
    price: Decimal = Field(..., description="Movie price")
    genres: List[str] = Field(default_factory=list, description="Movie genres")


class CartItemResponseSchema(BaseModel):
    """Schema for cart item response with movie details"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    cart_id: int
    movie_id: int
    added_at: datetime
    movie: Optional[MovieInCartSchema] = Field(None, description="Movie details")
    is_purchased: bool = Field(False, description="Whether this movie was already purchased")


class CartResponseSchema(BaseModel):
    """Schema for cart response"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    cart_items: List[CartItemResponseSchema] = []
    total_price: Decimal = Field(Decimal('0.00'), description="Total price of available items")
    total_items: int = Field(0, description="Total number of items")
    available_items: int = Field(0, description="Number of items available for purchase")


class CartItemRemoveSchema(BaseModel):
    """Schema for removing a movie from cart"""

    movie_id: int = Field(..., description="ID of the movie to remove from cart", gt=0)


class CartSummarySchema(BaseModel):
    """Schema for cart summary (without detailed items)"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    items_count: int = Field(..., description="Number of items in cart")
    available_items_count: int = Field(0, description="Number of items available for purchase")
    total_price: Decimal = Field(Decimal('0.00'), description="Total price of available items")


class CartValidationResponseSchema(BaseModel):
    """Schema for cart validation response"""
    
    available_movies: List[int] = Field(..., description="List of movie IDs available for purchase")
    purchased_movies: List[int] = Field(..., description="List of movie IDs already purchased")
    unavailable_movies: List[int] = Field(..., description="List of movie IDs not available")
    total_price: Decimal = Field(..., description="Total price of available movies")
    message: str = Field(..., description="Validation message")
