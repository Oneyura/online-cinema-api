from typing import List

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Enum, Numeric
from sqlalchemy.orm import relationship
import enum
from datetime import datetime

from sqlalchemy.orm.attributes import Mapped

from src.database.models.payments import PaymentsItemModel
from src.database.models.base import Base


class OrderStatusEnum(enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(OrderStatusEnum), nullable=False)
    total_amount = Column(Numeric(10, 2))

    payments: Mapped[List["PaymentsModel"]] = relationship("PaymentsModel", back_populates="order")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    movie_id = Column(Integer, ForeignKey("movies.id"), nullable=False)
    price_at_order = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    payments_items: Mapped[List["PaymentsItemModel"]] = relationship("PaymentsItemModel", back_populates="order_item")

