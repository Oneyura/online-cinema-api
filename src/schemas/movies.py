from datetime import date, datetime
from typing import List, Optional, Literal
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, condecimal


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


class GenreCreate(GenreBase):
    pass

class ActorCreate(ActorBase):
    pass

class DirectorCreate(DirectorBase):
    pass

class CertificationCreate(CertificationBase):
    pass

class MovieCreate(BaseModel):
    uuid: UUID = Field(
        ...,
        example="123e4567-e89b-12d3-a456-426614174000",
        description="Unique identifier for the movie"
    )
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
    star_ids: Optional[List[int]] = Field(
        None,
        description="List of Star (Actor) IDs associated with the movie"
    )

    model_config = ConfigDict(from_attributes=True) #

class MovieUpdate(MovieCreate):
    uuid: Optional[UUID] = None
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
    star_ids: Optional[List[int]] = None


class MovieResponseNested(BaseModel):
    id: int
    uuid: UUID
    name: str
    year: int
    imdb: float
    model_config = ConfigDict(from_attributes=True)


class GenreResponse(GenreBase):
    id: int
    movies: List["MovieResponseNested"] = []
    model_config = ConfigDict(from_attributes=True)


class ActorResponse(ActorBase):
    id: int
    movies: List["MovieResponseNested"] = []
    model_config = ConfigDict(from_attributes=True)


class DirectorResponse(DirectorBase):
    id: int
    movies: List["MovieResponseNested"] = []
    model_config = ConfigDict(from_attributes=True)


class CertificationResponse(CertificationBase):
    id: int
    movies: List["MovieResponseNested"] = []
    model_config = ConfigDict(from_attributes=True)


class MovieResponse(MovieCreate):
    id: int = Field(..., description="The unique ID of the movie")
    certification: CertificationResponse
    genres: List[GenreResponse] = []
    directors: List[DirectorResponse] = []
    stars: List[ActorResponse] = []

    genre_ids: Optional[List[int]] = Field(None, exclude=True)
    director_ids: Optional[List[int]] = Field(None, exclude=True)
    star_ids: Optional[List[int]] = Field(None, exclude=True)

    model_config = ConfigDict(from_attributes=True)

# Визначте базову схему для коментарів без вкладених відповідей, щоб уникнути рекурсії
class CommentBase(BaseModel):
    id: int
    user_id: int
    movie_id: int
    text: str
    created_at: datetime.datetime
    parent_comment_id: Optional[int] = None # Додано

    class Config:
        from_attributes = True

# Схема для створення коментаря
class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    parent_comment_id: Optional[int] = None

# Схема для відповіді на коментар, що включає інформацію про користувача та, можливо, вкладені відповіді
class CommentResponse(CommentBase):
    user: "UserModelResponse" # Використовуйте схему для UserModel, яку ви вже маєте
    replies: Optional[List["CommentResponse"]] = None # Необхідно для вкладених відповідей

# Оновіть CommentResponse для рекурсії, якщо хочете бачити вкладені відповіді
# Це вимагає використання `update_forward_refs()` після визначення всіх схем
class CommentResponseNested(CommentBase):
    user: "UserModelResponse"
    replies: Optional[List["CommentResponseNested"]] = None # Для вкладених відповідей
class UserResponseNested(BaseModel):
    id: int # Додайте поля, які ви очікуєте від UserResponseNested
    username: str # Наприклад, id та username
    model_config = ConfigDict(from_attributes=True)


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


MovieResponseNested.model_rebuild()
GenreResponse.model_rebuild()
ActorResponse.model_rebuild()
DirectorResponse.model_rebuild()
CertificationResponse.model_rebuild()
MovieResponse.model_rebuild()
CommentResponse.model_rebuild()
MovieLikeResponse.model_rebuild()
MovieRatingResponse.model_rebuild()
FavoriteMovieResponse.model_rebuild()
CommentResponse.update_forward_refs()
CommentResponseNested.update_forward_refs()
