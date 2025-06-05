import datetime
from sqlalchemy import (
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    DECIMAL,
    Text
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import Optional

from src.database.models.movies import MovieModel
from src.database.models.base import Base


class UserModel(Base):
    pass


class CommentModel(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="comments")
    movie: Mapped["MovieModel"] = relationship("MovieModel", back_populates="comments")

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, user_id={self.user_id}, movie_id={self.movie_id}, text='{self.text[:20]}...')>"


class MovieLikeModel(Base):
    __tablename__ = "movie_likes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    is_liked: Mapped[bool] = mapped_column(Boolean, nullable=False) # True for like, False for dislike
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="movie_likes")
    movie: Mapped["MovieModel"] = relationship("MovieModel", back_populates="movie_likes")


class FavoriteMovieModel(Base):
    __tablename__ = "favorite_movies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    added_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="favorite_movies")
    movie: Mapped["MovieModel"] = relationship("MovieModel", back_populates="favorite_movies")

    __table_args__ = (UniqueConstraint("user_id", "movie_id", name="unique_favorite_per_user"),)


class MovieRatingModel(Base):
    __tablename__ = "movie_ratings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False) # 1-10 scale
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="movie_ratings")
    movie: Mapped["MovieModel"] = relationship("MovieModel", back_populates="movie_ratings")


class PurchaseModel(Base):
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    purchase_date: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)
    price_paid: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="purchases")
    movie: Mapped["MovieModel"] = relationship("MovieModel", back_populates="purchases")
