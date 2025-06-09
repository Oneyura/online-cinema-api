from datetime import datetime
from typing import List

from sqlalchemy import ForeignKey, Integer, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class CartModel(Base):
    """
    Shopping cart model.
    Each user has exactly one cart.
    """

    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    user: Mapped["UserModel"] = relationship("UserModel", back_populates="cart")
    cart_items: Mapped[List["CartItemModel"]] = relationship(
        "CartItemModel", back_populates="cart", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<CartModel(id={self.id}, user_id={self.user_id}, created_at={self.created_at})>"


class CartItemModel(Base):
    """
    Shopping cart item model.
    Represents a single movie in a user's cart.
    A movie can appear in a cart only once.
    """

    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    cart: Mapped["CartModel"] = relationship("CartModel", back_populates="cart_items")
    movie: Mapped["MovieModel"] = relationship("MovieModel")

    # Constraints
    __table_args__ = (UniqueConstraint("cart_id", "movie_id", name="uq_cart_items_cart_id_movie_id"),)

    def __repr__(self):
        return (
            f"<CartItemModel(id={self.id}, cart_id={self.cart_id}, movie_id={self.movie_id}, added_at={self.added_at})>"
        )
