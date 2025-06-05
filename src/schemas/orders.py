from pydantic import BaseModel
from typing import List
from datetime import datetime
from decimal import Decimal
from enum import Enum

class OrderStatusEnum(str, Enum):
    pending = "pending"
    paid = "paid"
    canceled = "canceled"

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

    class Config:
        orm_mode = True
