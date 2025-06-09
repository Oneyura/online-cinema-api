from datetime import datetime
from typing import List

from pydantic import BaseModel, Field, ConfigDict


class CartItemAddSchema(BaseModel):
    """Schema for adding a movie to cart"""

    movie_id: int = Field(..., description="ID of the movie to add to cart", gt=0)


class CartItemResponseSchema(BaseModel):
    """Schema for cart item response"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    cart_id: int
    movie_id: int
    added_at: datetime


class CartResponseSchema(BaseModel):
    """Schema for cart response"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    cart_items: List[CartItemResponseSchema] = []


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
