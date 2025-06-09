from typing import Optional, List
from uuid import UUID
from sqlalchemy import (
    String,
    Float,
    Text,
    DECIMAL,
    UniqueConstraint,
    ForeignKey,
    Table,
    Column,
    Integer,
    Boolean, DateTime,
)
import datetime
from sqlalchemy.orm import mapped_column, Mapped, relationship

from src.database.models.accounts import UserModel
from src.database.models.base import Base

MoviesGenresModel = Table(
    "movies_genres",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    Column(
        "genre_id",
        ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True, nullable=False),
)

MoviesDirectorsModel = Table(
    "movies_directors",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    Column(
        "director_id",
        ForeignKey("directors.id", ondelete="CASCADE"), primary_key=True, nullable=False),
)

MoviesActorsModel = Table(
    "movies_actors",
    Base.metadata,
    Column(
        "movie_id",
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True, nullable=False),
    Column(
        "actor_id", # Updated column name to actor_id
        ForeignKey("actors.id", ondelete="CASCADE"), primary_key=True, nullable=False),
)


class GenreModel(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    movies: Mapped[List["MovieModel"]] = relationship(
        "MovieModel",
        secondary=MoviesGenresModel,
        back_populates="genres"
    )

    def __repr__(self) -> str:
        return f"<Genre(id='{self.id}', name='{self.name}')>"


class ActorModel(Base):
    __tablename__ = "actors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    movies: Mapped[List["MovieModel"]] = relationship(
        "MovieModel",
        secondary=MoviesActorsModel,
        back_populates="actors"
    )

    def __repr__(self) -> str:
        return f"<Actor(id='{self.id}', name='{self.name}')>"


class DirectorModel(Base):
    __tablename__ = "directors"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    movies: Mapped[List["MovieModel"]] = relationship(
        "MovieModel",
        secondary=MoviesDirectorsModel,
        back_populates="directors"
    )


class CertificationModel(Base):
    __tablename__ = "certifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    movies: Mapped[List["MovieModel"]] = relationship(
        "MovieModel",
        back_populates="certification"
    )

    def __repr__(self) -> str:
        return f"<Certification(id={self.id}, name='{self.name}')>"


class MovieModel(Base):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uuid: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    year: Mapped[int] = mapped_column(nullable=False)
    time: Mapped[int] = mapped_column(nullable=False)
    imdb: Mapped[float] = mapped_column(Float, nullable=False)
    votes: Mapped[int] = mapped_column(nullable=False)
    meta_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gross: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    comments: Mapped[List["CommentModel"]] = relationship(
        "CommentModel",
        back_populates="movie"
    )
    movie_likes: Mapped[List["MovieLikeModel"]] = relationship(
        "MovieLikeModel",
        back_populates="movie"
    )
    movie_ratings: Mapped[List["MovieRatingModel"]] = relationship(
        "MovieRatingModel",
        back_populates="movie"
    )
    favorite_movies: Mapped[List["FavoriteMovieModel"]] = relationship(
        "FavoriteMovieModel",
        back_populates="movie"
    )
    purchases: Mapped[List["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="movie"
    )
    certification_id: Mapped[int] = mapped_column(
        ForeignKey("certifications.id"),
        nullable=False,
    )

    certification: Mapped["CertificationModel"] = relationship(
        "CertificationModel",
        back_populates="movies"
    )

    genres: Mapped[List["GenreModel"]] = relationship(
        "GenreModel",
        secondary=MoviesGenresModel,
        back_populates="movies"
    )

    directors: Mapped[List["DirectorModel"]] = relationship(
        "DirectorModel",
        secondary=MoviesDirectorsModel,
        back_populates="movies"
    )

    actors: Mapped[List["ActorModel"]] = relationship(
        "ActorModel",
        secondary=MoviesActorsModel,
        back_populates="movies"
    )

    __table_args__ = (
        UniqueConstraint("name", "year", "time", name="unique_name_year_time_constraint"),
    )

    def __repr__(self) -> str:
        return f"<Movie(id={self.id}, name='{self.name}', year={self.year})>"


class CommentModel(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.now)

    # Додайте поле для батьківського коментаря
    parent_comment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )

    user: Mapped["UserModel"] = relationship("UserModel", back_populates="comments")
    movie: Mapped["MovieModel"] = relationship("MovieModel", back_populates="comments")

    # Додайте зв'язки для ієрархії коментарів
    parent_comment: Mapped[Optional["CommentModel"]] = relationship(
        "CommentModel", remote_side=[id], back_populates="replies", lazy="joined"
    )
    replies: Mapped[List["CommentModel"]] = relationship(
        "CommentModel", back_populates="parent_comment", lazy="joined"
    )

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
