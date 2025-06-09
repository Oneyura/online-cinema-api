from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from enum import Enum

class OrderStatusEnum(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"

class OrderItemSchema(BaseModel):
    movie_id: int
    price_at_order: Decimal

class OrderCreateSchema(BaseModel):
    movie_ids: List[int]

class OrderResponseSchema(BaseModel):
    id: int
    created_at: datetime
    status: OrderStatusEnum
    total_amount: Decimal
    items: List[OrderItemSchema]
    payment_url: Optional[HttpUrl]

    class Config:
        orm_mode = True


