from datetime import datetime
import enum
from decimal import Decimal
from typing import List
from src.database.models.accounts import UserModel


from sqlalchemy.sql.sqltypes import Numeric

from src.database.base import Base

from sqlalchemy import (
    ForeignKey,
    String,
    Boolean,
    DateTime,
    Enum,
    Integer,
    func,
    Text,
    Date,
    UniqueConstraint
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
    validates
)


class PaymentStatus(enum.Enum):
    SUCCESSFUL = enum.auto()
    CANCELED = enum.auto()
    REFUNDED = enum.auto()


class Payments(Base):

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    order_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    external_payment_id: Mapped[str] = mapped_column(String, nullable=True)
    order: Mapped["Order"] = relationship("Order", back_populates="payments")
    payment_items: Mapped[List["PaymentsItem"]] = relationship("PaymentsItem", back_populates="payment", cascade="all, delete-orphan")
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="payments")


class PaymentsItem(Base):
    __tablename__ = "paymentsitem"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    payment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False
    )
    order_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False
    )
    price_at_payment: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )

    payment: Mapped["Payments"] = relationship("Payments", back_populates="payment_items")
    order_item: Mapped["OrderItem"] = relationship("OrderItem", back_populates="payments_items")
