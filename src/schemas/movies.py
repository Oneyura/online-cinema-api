from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, condecimal

from src.schemas.auth import UserPublicResponseSchema


# --- Base Schemas (often used for input or simple output) ---
class GenreBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, example="Action")
    model_config = ConfigDict(from_attributes=True)


class ActorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, example="Tom Hanks")
    model_config = ConfigDict(from_attributes=True)


class DirectorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, example="Christopher Nolan")
    model_config = ConfigDict(from_attributes=True)


class CertificationBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, example="PG-13")
    model_config = ConfigDict(from_attributes=True)


# --- Create Schemas (for incoming request bodies) ---
class GenreCreate(GenreBase):
    pass


class ActorCreate(ActorBase):
    pass


class DirectorCreate(DirectorBase):
    pass


class CertificationCreate(CertificationBase):
    pass


class GenreCreateResponse(BaseModel):
    id: int = Field(..., description="Unique identifier of the genre.")
    name: str = Field(..., description="Genre name")
    model_config = ConfigDict(from_attributes=True)


class ActorCreateResponse(BaseModel):
    id: int = Field(..., description="Unique identifier of the actor.")
    name: str = Field(..., description="Actor's name")
    model_config = ConfigDict(from_attributes=True)


class DirectorCreateResponse(BaseModel):
    id: int = Field(..., description="Unique identifier of the director.")
    name: str = Field(..., description="Director's name")
    model_config = ConfigDict(from_attributes=True)


class CertificationCreateResponse(BaseModel):
    id: int = Field(..., description="Unique identifier of the certification.")
    name: str = Field(..., description="Certification name")
    model_config = ConfigDict(from_attributes=True)


# --- Movie Schemas ---

class MovieCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        example="Inception",
        description="Movie title"
    )
    year: int = Field(
        ...,
        gt=1800,
        lt=date.today().year + 5,
        example=2010,
        description="Release year"
    )
    time: int = Field(
        ...,
        gt=0,
        example=148,
        description="Duration in minutes"
    )
    imdb: float = Field(
        ...,
        ge=0.0,
        le=10.0,
        example=8.8,
        description="IMDb rating (0.0 to 10.0)"
    )
    votes: int = Field(
        ...,
        ge=0,
        example=2400000,
        description="Number of IMDb votes"
    )
    meta_score: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        example=74.0,
        description="Metascore (0.0 to 100.0)"
    )
    gross: Optional[float] = Field(
        None,
        ge=0.0,
        example=292.6,
        description="Gross revenue (in millions)"
    )
    description: str = Field(
        ...,
        min_length=10,
        example="A thief who steals corporate secrets "
                "through use of dream-sharing technology...",
        description="Movie synopsis")
    price: condecimal(max_digits=10, decimal_places=2) = Field(
        ...,
        gt=0,
        example=9.99,
        description="Price of the movie"
    )
    certification_id: int = Field(
        ...,
        example=1,
        description="ID of the movie's certification (e.g., PG-13, R)"
    )

    genre_ids: Optional[List[int]] = Field(
        None,
        description="List of Genre IDs associated with the movie"
    )
    director_ids: Optional[List[int]] = Field(
        None,
        description="List of Director IDs associated with the movie"
    )
    actor_ids: Optional[List[int]] = Field(
        None,
        description="List of Actor IDs associated with the movie"
    )

    model_config = ConfigDict(from_attributes=True)


class MovieUpdate(MovieCreate):
    # UUID should not be updated.
    name: Optional[str] = None
    year: Optional[int] = None
    time: Optional[int] = None
    imdb: Optional[float] = None
    votes: Optional[int] = None
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: Optional[str] = None
    price: Optional[condecimal(max_digits=10, decimal_places=2)] = None
    certification_id: Optional[int] = None
    genre_ids: Optional[List[int]] = None
    director_ids: Optional[List[int]] = None
    actor_ids: Optional[List[int]] = None


# --- Flat Response Schemas for nested objects within MovieCreateResponse and MovieResponse ---
class DirectorFlatResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class ActorFlatResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class GenreFlatResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


class CertificationFlatResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)


# --- Movie Response for POST/PUT (uses flat nested schemas) ---
class MovieCreateResponse(BaseModel):
    id: int
    uuid: UUID
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: str
    price: Decimal
    certification: Optional[CertificationFlatResponse] = None
    genres: List[GenreFlatResponse] = []
    directors: List[DirectorFlatResponse] = []
    actors: List[ActorFlatResponse] = []

    model_config = ConfigDict(from_attributes=True)


# --- Movie Response for detailed GET requests (uses flat nested schemas) ---
class MovieResponse(BaseModel):
    id: int = Field(..., description="The unique ID of the movie")
    uuid: UUID
    name: str
    year: int
    time: int
    imdb: float
    votes: int
    meta_score: Optional[float] = None
    gross: Optional[float] = None
    description: str
    price: Decimal
    certification: Optional[CertificationFlatResponse] = None
    genres: List[GenreFlatResponse] = []
    directors: List[DirectorFlatResponse] = []
    actors: List[ActorFlatResponse] = []
    # Додано для повноти, якщо фільм має відгуки, оцінки, лайки
    movie_likes: List["MovieLikeResponse"] = []
    movie_ratings: List["MovieRatingResponse"] = []
    comments: List["CommentResponse"] = []

    model_config = ConfigDict(from_attributes=True)


# --- Schemas for lists of movies, or nested within Directors/Actors/Genres/Certifications ---
class MovieResponseNested(BaseModel):
    id: int
    uuid: UUID
    name: str
    year: int
    imdb: float
    genres: List[GenreFlatResponse] = []
    directors: List[DirectorFlatResponse] = []
    actors: List[ActorFlatResponse] = []
    model_config = ConfigDict(from_attributes=True)


class MovieResponseNestedForGenres(BaseModel):
    id: int
    uuid: UUID
    name: str
    year: int
    imdb: float
    directors: List[DirectorFlatResponse] = []
    actors: List[ActorFlatResponse] = []
    certification: Optional[CertificationFlatResponse] = None
    model_config = ConfigDict(from_attributes=True)


class MovieResponseNestedForActor(BaseModel):
    id: int
    uuid: UUID
    name: str
    year: int
    imdb: float
    directors: List[DirectorFlatResponse] = []
    genres: List[GenreFlatResponse] = []
    certification: Optional[CertificationFlatResponse] = None
    model_config = ConfigDict(from_attributes=True)


class MovieResponseForDirector(BaseModel):
    id: int
    uuid: UUID
    name: str
    year: int
    imdb: float
    genres: List[GenreFlatResponse] = []
    actors: List[ActorFlatResponse] = []
    certification: Optional[CertificationFlatResponse] = None
    model_config = ConfigDict(from_attributes=True)


class GenreResponse(GenreBase):
    id: int
    movies: List["MovieResponseNestedForGenres"] = []
    model_config = ConfigDict(from_attributes=True)


class ActorResponse(ActorBase):
    id: int
    movies: List["MovieResponseNestedForActor"] = []
    model_config = ConfigDict(from_attributes=True)


class DirectorResponse(DirectorBase):
    id: int
    movies: List[MovieResponseForDirector] = []
    model_config = ConfigDict(from_attributes=True)


class CertificationResponse(CertificationBase):
    id: int
    movies: List["MovieResponseNested"] = []
    model_config = ConfigDict(from_attributes=True)


# DirectorUpdate schema (already correct from previous discussion)
class DirectorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="New name for the director. Must be unique if provided.")
    model_config = ConfigDict(from_attributes=True)


# --- Comment Schemas ---
class CommentBase(BaseModel):
    id: int
    user_id: int
    movie_id: int
    text: str
    created_at: datetime
    parent_comment_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    parent_comment_id: Optional[int] = None


class CommentResponse(CommentBase):
    user: UserPublicResponseSchema
    # Self-referencing list for nested comments
    replies: Optional[List["CommentResponse"]] = None


class CommentResponseNested(CommentBase):
    user: UserPublicResponseSchema
    # Self-referencing list for nested comments
    replies: Optional[List["CommentResponseNested"]] = None


# --- Like/Rating/Favorite Schemas ---
class MovieLikeCreate(BaseModel):
    is_liked: bool = Field(
        ...,
        description="True for like, False for dislike",
        example=True
    )


class MovieLikeResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    is_liked: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MovieRatingCreate(BaseModel):
    rating: int = Field(
        ...,
        ge=1,
        le=10,
        description="Rating on a 1-10 scale",
        example=9
    )


class MovieRatingResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    rating: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FavoriteMovieCreate(BaseModel):
    pass


class FavoriteMovieResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    added_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- Rebuild Pydantic models for forward references ---
MovieResponseNested.model_rebuild()
MovieResponseNestedForGenres.model_rebuild()
MovieResponseNestedForActor.model_rebuild()
MovieResponseForDirector.model_rebuild()
GenreResponse.model_rebuild()
ActorResponse.model_rebuild()
DirectorResponse.model_rebuild()
CertificationResponse.model_rebuild()
MovieResponse.model_rebuild()
CommentResponse.model_rebuild()
CommentResponseNested.model_rebuild()
MovieLikeResponse.model_rebuild()
MovieRatingResponse.model_rebuild()
FavoriteMovieResponse.model_rebuild()
