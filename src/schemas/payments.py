# todo: PaymentCreate, PaymentRead, PaymentItemRead
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_serializer, computed_field
from pydantic_core.core_schema import json_schema


class PaymentItemResponseSchema(BaseModel):
    id: int
    price_at_payment: float
    order_item_id: int

    model_config = {
        "from_attributes": True,
    }


class PaymentBaseSchema(BaseModel):
    id: int
    order_id: int
    created_at: datetime
    status: str
    amount: float
    external_payment_id: Optional[str] = None

    model_config = {
        "from_attributes": True,
    }


class PaymentDetailResponseSchema(PaymentBaseSchema):
    user_id: int
    payment_items: List[PaymentItemResponseSchema] = []

    model_config = {
        "from_attributes": True,
    }


class PaymentListResponseSchema(BaseModel):
    payments: List[PaymentDetailResponseSchema]
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    total_pages: int
    total_items: int

    model_config = {
        "from_attributes": True,
    }


class PaymentCreateSchema(BaseModel):
    order_id: int
    payment_method: str = "CARD"
