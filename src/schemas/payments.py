#todo: PaymentCreate, PaymentRead, PaymentItemRead
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_serializer
from pydantic_core.core_schema import json_schema


class PaymentItemResponseSchema(BaseModel):
    id: int
    price_at_payment: float
    order_items_movie_name: str

    @field_serializer("order_items_movie_name", mode="plain")
    def get_movie_name(self, obj):
        return obj.order_item.movie.name if obj.order_item and obj.order_item.movie else None

    model_config = {
        "from_attributes": True,
    }


class PaymentBaseSchema(BaseModel):
    id: int
    order_id: int
    created_at: datetime
    status: str
    amount: float
    external_payment_id: str



class PaymentDetailResponseSchema(PaymentBaseSchema):
    user_name: str
    payment_items: List[PaymentItemResponseSchema]

    @field_serializer("user_name", mode="plain")
    def get_user_name(self, obj):
        return obj.user.name if obj.user else None #TODO add relationship field to user_model


class PaymentListResponseSchema(BaseModel):
    payments: List[PaymentBaseSchema]
    prev_page: Optional[str]
    next_page: Optional[str]
    total_pages: int
    total_items: int

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                #todo create examples payment
            ]
        }
    }
