# routes/movie.py
import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional, Literal

from sqlalchemy.orm import  selectinload

from src.database.models import CommentModel
from src.database.models import UserModel
from src.config.dependencies import get_db
from src.database.models.movies import (
    MovieModel,
    GenreModel,
    DirectorModel,
    ActorModel,
    CertificationModel,
    MoviesGenresModel,
    MoviesDirectorsModel,
)
from src.database.models.orders import OrderItem
from src.database.models.movies import (
    MovieLikeModel,
    MovieRatingModel,
    FavoriteMovieModel,
)

from src.schemas.movies import (
    MovieCreate,
    MovieUpdate,
    MovieResponse,
    MovieResponseNested,
    GenreResponse,
    ActorResponse,
    DirectorResponse,
    CertificationResponse,
    GenreCreate,
    ActorCreate,
    DirectorCreate,
    CertificationCreate, CommentResponseNested, DirectorCreateResponse, MovieCreateResponse, DirectorUpdate,
)
from src.schemas.movies import (
    CommentCreate,
    CommentResponse,
    MovieLikeResponse,
    MovieRatingCreate,
    MovieRatingResponse,
    FavoriteMovieResponse
)
from src.config.dependencies import get_current_user, get_current_moderator

router = APIRouter(prefix="/movies", tags=["Movies"])


# --- Helper function for applying filters and sorting ---
async def apply_movie_filters_and_sort(
        query,
        db: AsyncSession,
        search: Optional[str] = None,
        year: Optional[int] = None,
        imdb_min: Optional[float] = None,
        imdb_max: Optional[float] = None,
        genre_name: Optional[str] = None,
        director_name: Optional[str] = None,
        actor_name: Optional[str] = None,
        sort_by: Literal["price", "year", "imdb", "votes", "name"] = "name",
        sort_order: Literal["asc", "desc"] = "asc"
) -> select:
    """Applies common filters and sorting to a movie query."""

    # Search by title, description, actor, or director
    if search:
        query = query.filter(
            or_(
                MovieModel.name.ilike(f"%{search}%"),
                MovieModel.description.ilike(f"%{search}%"),
                MovieModel.directors.any(DirectorModel.name.ilike(f"%{search}%")),
                MovieModel.actors.any(ActorModel.name.ilike(f"%{search}%"))
            )
        )

    if year:
        query = query.filter(MovieModel.year == year)

    if imdb_min is not None:
        query = query.filter(MovieModel.imdb >= imdb_min)
    if imdb_max is not None:
        query = query.filter(MovieModel.imdb <= imdb_max)

    if genre_name:
        query = query.filter(MovieModel.genres.any(GenreModel.name.ilike(f"%{genre_name}%")))

    if director_name:
        query = query.filter(MovieModel.directors.any(DirectorModel.name.ilike(f"%{director_name}%")))

    if actor_name:
        query = query.filter(MovieModel.actors.any(ActorModel.name.ilike(f"%{actor_name}%")))

    sort_column = None
    if sort_by == "price":
        sort_column = MovieModel.price
    elif sort_by == "year":
        sort_column = MovieModel.year
    elif sort_by == "imdb":
        sort_column = MovieModel.imdb
    elif sort_by == "votes":
        sort_column = MovieModel.votes
    elif sort_by == "name":
        sort_column = MovieModel.name

    if sort_column:
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    else:
        # Apply default order_by from model if no specific sort_by is provided
        # Assuming MovieModel.default_order_by() returns a valid SQLAlchemy order_by clause
        default_order = getattr(MovieModel, 'default_order_by', lambda: None)()
        if default_order is not None:
            if isinstance(default_order, tuple):
                query = query.order_by(*default_order)
            else:
                query = query.order_by(default_order)


    return query


# --- Browse Movie Catalog (Pagination, Filter, Sort, Search) ---
@router.get("/", response_model=List[MovieResponseNested])
async def browse_movies(
        db: AsyncSession = Depends(get_db),
        page: int = Query(1, ge=1, description="Page number for pagination"),
        limit: int = Query(10, ge=1, le=100, description="Number of items per page"),
        search: Optional[str] = Query(None, description="Search by title, description, actor, or director"),
        year: Optional[int] = Query(None, description="Filter by release year"),
        imdb_min: Optional[float] = Query(None, ge=0.0, le=10.0, description="Minimum IMDb rating"),
        imdb_max: Optional[float] = Query(None, ge=0.0, le=10.0, description="Maximum IMDb rating"),
        genre_name: Optional[str] = Query(None, description="Filter by genre name (e.g., Action)"),
        director_name: Optional[str] = Query(None, description="Filter by director's name"),
        actor_name: Optional[str] = Query(None, description="Filter by actor's name"),
        sort_by: Literal["price", "year", "imdb", "votes", "name"] = Query("name", description="Attribute to sort by"),
        sort_order: Literal["asc", "desc"] = Query("asc", description="Sort order (ascending or descending)")
) -> List[MovieResponseNested]:
    """
    Browse the movie catalog with pagination, search, filter, and sort options.
    """
    query = select(MovieModel)

    # Apply filters and sorting
    query = await apply_movie_filters_and_sort(
        query, db, search, year, imdb_min, imdb_max, genre_name, director_name, actor_name, sort_by, sort_order
    )

    # Pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    movies = result.scalars().all()
    return movies


# --- View Detailed Movie Description ---
@router.get("/{movie_id}", response_model=MovieResponse)
async def get_movie_details(
        movie_id: int,
        db: AsyncSession = Depends(get_db)
) -> MovieResponse:
    """
    View detailed description of a specific movie.
    """
    query = select(MovieModel).filter(MovieModel.id == movie_id).options(
        # Eager load related data for detailed view
        selectinload(MovieModel.certification),
        selectinload(MovieModel.genres),
        selectinload(MovieModel.directors),
        selectinload(MovieModel.actors)
    )
    result = await db.execute(query)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    return movie


# --- Like/Dislike Movies ---
@router.post("/{movie_id}/like", response_model=MovieLikeResponse)
async def like_dislike_movie(
        movie_id: int,
        is_liked: bool = Query(..., description="True for like, False for dislike"),
        current_user: UserModel = Depends(get_current_user),  # Requires authentication
        db: AsyncSession = Depends(get_db)
) -> MovieLikeResponse:
    """
    Like or dislike a movie. A user can only have one like/dislike status per movie.
    """
    movie = await db.execute(select(MovieModel).filter_by(id=movie_id))
    if not movie.scalars().first():
        raise HTTPException(status_code=404, detail="Movie not found")

    # Check for existing like/dislike
    existing_like = await db.execute(
            select(MovieLikeModel).filter_by(user_id=current_user.id, movie_id=movie_id)
    )
    existing_like = existing_like.scalars().first()

    if existing_like:
        if existing_like.is_liked == is_liked:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Movie already {'liked' if is_liked else 'disliked'} by this user."
            )
        # Update existing like/dislike
        existing_like.is_liked = is_liked
        existing_like.created_at = datetime.datetime.now()
        db.add(existing_like)
        await db.commit()
        await db.refresh(existing_like)
        return existing_like
    else:
        # Create new like/dislike
        new_like = MovieLikeModel(
            user_id=current_user.id,
            movie_id=movie_id,
            is_liked=is_liked
        )
        db.add(new_like)
        await db.commit()
        await db.refresh(new_like)
        return new_like


# --- Write Comments on Movies ---
@router.post("/{movie_id}/comments", response_model=CommentResponse)
async def write_comment(
        movie_id: int,
        comment: CommentCreate,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
) -> CommentResponse:
    """
    Write a comment on a movie, or reply to an existing comment.
    """
    # Check if movie exists
    movie_exists = await db.execute(select(MovieModel.id).filter_by(id=movie_id))
    if not movie_exists.scalars().first():
        raise HTTPException(status_code=404, detail="Movie not found")

    # If parent_comment_id is provided, check if it exists and belongs to the same movie
    if comment.parent_comment_id:
        parent_comment = await db.execute(
            select(CommentModel).filter_by(id=comment.parent_comment_id, movie_id=movie_id)
        )
        if not parent_comment.scalars().first():
            raise HTTPException(status_code=400, detail="Parent comment not found or does not belong to this movie.")

    new_comment = CommentModel(
        user_id=current_user.id,
        movie_id=movie_id,
        text=comment.text,
        parent_comment_id=comment.parent_comment_id
    )
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)

    await db.refresh(new_comment, attribute_names=['user', 'parent_comment', 'replies'])
    return new_comment


@router.get("/{movie_id}/comments", response_model=List[CommentResponseNested])
async def get_movie_comments(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1, le=100)
) -> List[CommentResponseNested]:
    """
    Get all top-level comments for a specific movie, with nested replies.
    """
    query = (
        select(CommentModel)
        .filter(CommentModel.movie_id == movie_id)
        .filter(CommentModel.parent_comment_id.is_(None))
    )

    query = query.order_by(CommentModel.created_at.desc())

    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # Eager load user for comments and recursively load replies
    query = query.options(
        selectinload(CommentModel.user),
        selectinload(CommentModel.replies).selectinload(CommentModel.user).selectinload(CommentModel.replies)
    )

    result = await db.execute(query)
    comments = result.scalars().unique().all()
    return comments


# --- Add/Remove Movies from Favorites ---
@router.post("/{movie_id}/favorite", response_model=FavoriteMovieResponse)
async def add_movie_to_favorites(
        movie_id: int,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
) -> FavoriteMovieResponse:
    """
    Add a movie to the current user's favorites list.
    """
    movie_exists = await db.execute(select(MovieModel.id).filter_by(id=movie_id))
    if not movie_exists.scalars().first():
        raise HTTPException(status_code=404, detail="Movie not found")

    existing_favorite = await db.execute(
        select(FavoriteMovieModel).filter_by(user_id=current_user.id, movie_id=movie_id)
    )
    if existing_favorite.scalars().first():
        raise HTTPException(status_code=409, detail="Movie already in favorites")

    new_favorite = FavoriteMovieModel(user_id=current_user.id, movie_id=movie_id)
    db.add(new_favorite)
    await db.commit()
    await db.refresh(new_favorite)
    return new_favorite


@router.delete("/{movie_id}/favorite", status_code=status.HTTP_204_NO_CONTENT)
async def remove_movie_from_favorites(
        movie_id: int,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
) -> None:
    """
    Remove a movie from the current user's favorites list.
    """
    favorite_item = await db.execute(
        select(FavoriteMovieModel).filter_by(user_id=current_user.id, movie_id=movie_id)
    )
    favorite_item = favorite_item.scalars().first()

    if not favorite_item:
        raise HTTPException(status_code=404, detail="Movie not found in favorites")

    await db.delete(favorite_item)
    await db.commit()


@router.get("/favorites", response_model=List[MovieResponseNested])
async def get_favorite_movies(
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1, le=100),
        search: Optional[str] = Query(None),
        year: Optional[int] = Query(None),
        imdb_min: Optional[float] = Query(None),
        imdb_max: Optional[float] = Query(None),
        genre_name: Optional[str] = Query(None),
        director_name: Optional[str] = Query(None),
        actor_name: Optional[str] = Query(None),
        sort_by: Literal["price", "year", "imdb", "votes", "name"] = Query("name"),
        sort_order: Literal["asc", "desc"] = Query("asc")
) -> List[MovieResponseNested]:
    """
    Get the current user's favorite movies with search, filter, and sort options.
    """
    query = select(MovieModel).join(FavoriteMovieModel).filter(
        FavoriteMovieModel.user_id == current_user.id
    )

    query = await apply_movie_filters_and_sort(
        query, db, search, year, imdb_min, imdb_max, genre_name, director_name, actor_name, sort_by, sort_order
    )

    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    movies = result.scalars().all()
    return movies


# --- View Genres with Movie Count and Filter by Genre ---
@router.get("/genres", response_model=List[GenreResponse])
async def get_genres_with_counts(db: AsyncSession = Depends(get_db)) -> List[GenreResponse]:
    """
    Get a list of all genres with the count of movies in each.
    """
    genres_query = select(GenreModel).options(selectinload(GenreModel.movies))
    result = await db.execute(genres_query)
    genres = result.scalars().all()
    return genres


@router.get("/genres/{genre_id}/movies", response_model=List[MovieResponseNested])
async def get_movies_by_genre(
        genre_id: int,
        db: AsyncSession = Depends(get_db),
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1, le=100)
) -> List[MovieResponseNested]:
    """
    Get all movies belonging to a specific genre.
    """
    genre = await db.execute(select(GenreModel).filter_by(id=genre_id))
    if not genre.scalars().first():
        raise HTTPException(status_code=404, detail="Genre not found")

    query = (
        select(MovieModel)
        .join(MoviesGenresModel)
        .filter(MoviesGenresModel.c.genre_id == genre_id)
    )
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    movies = result.scalars().all()
    return movies


# --- Rate Movies ---
@router.post("/{movie_id}/rate", response_model=MovieRatingResponse)
async def rate_movie(
        movie_id: int,
        rating_data: MovieRatingCreate,
        current_user: UserModel = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
) -> MovieRatingResponse:
    """
    Rate a movie on a 10-point scale. Users can update their rating.
    """
    movie_exists = await db.execute(select(MovieModel.id).filter_by(id=movie_id))
    if not movie_exists.scalars().first():
        raise HTTPException(status_code=404, detail="Movie not found")

    existing_rating = await db.execute(
        select(MovieRatingModel).filter_by(user_id=current_user.id, movie_id=movie_id)
    )
    existing_rating = existing_rating.scalars().first()

    if existing_rating:
        existing_rating.rating = rating_data.rating
        existing_rating.created_at = datetime.datetime.now()
        db.add(existing_rating)
        await db.commit()
        await db.refresh(existing_rating)
        return existing_rating
    else:
        new_rating = MovieRatingModel(
            user_id=current_user.id,
            movie_id=movie_id,
            rating=rating_data.rating
        )
        db.add(new_rating)
        await db.commit()
        await db.refresh(new_rating)
        return new_rating


# --- Moderator Functionality (CRUD on Movies, Genres, Actors) ---

# Create Movie
@router.post("/", response_model=MovieResponse, status_code=status.HTTP_201_CREATED)
async def create_movie(
        movie: MovieCreate,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)  # Requires moderator role
) -> MovieCreateResponse:
    """
    Create a new movie (Moderator only).
    """
    # Check if certification_id exists
    cert = await db.execute(select(CertificationModel).filter_by(id=movie.certification_id))
    if not cert.scalars().first():
        raise HTTPException(status_code=400, detail="Certification ID not found")

    new_movie = MovieModel(
        uuid=movie.uuid,
        name=movie.name,
        year=movie.year,
        time=movie.time,
        imdb=movie.imdb,
        votes=movie.votes,
        meta_score=movie.meta_score,
        gross=movie.gross,
        description=movie.description,
        price=movie.price,
        certification_id=movie.certification_id
    )

    if movie.genre_ids:
        genres = await db.execute(select(GenreModel).filter(GenreModel.id.in_(movie.genre_ids)))
        found_genres = genres.scalars().all()
        if len(found_genres) != len(movie.genre_ids):
            raise HTTPException(status_code=400, detail="One or more genre IDs not found")
        new_movie.genres.extend(found_genres)

    if movie.director_ids:
        directors = await db.execute(select(DirectorModel).filter(DirectorModel.id.in_(movie.director_ids)))
        found_directors = directors.scalars().all()
        if len(found_directors) != len(movie.director_ids):
            raise HTTPException(status_code=400, detail="One or more director IDs not found")
        new_movie.directors.extend(found_directors)

    if movie.actor_ids:
        actors = await db.execute(select(ActorModel).filter(ActorModel.id.in_(movie.actor_ids)))
        found_actors = actors.scalars().all()
        if len(found_actors) != len(movie.actor_ids):
            raise HTTPException(status_code=400, detail="One or more actor IDs not found")
        new_movie.actors.extend(found_actors)

    try:
        db.add(new_movie)
        await db.commit()
        await db.refresh(new_movie)
        await db.refresh(new_movie, attribute_names=['certification', 'genres', 'directors', 'actors'])
        return new_movie
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not create movie: {e}")


# Update Movie
@router.put("/{movie_id}", response_model=MovieResponse)
async def update_movie(
        movie_id: int,
        movie_update: MovieUpdate,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)  # Requires moderator role
) -> MovieUpdate:
    """
    Update an existing movie by ID (Moderator only).
    """
    movie = await db.execute(select(MovieModel).filter_by(id=movie_id))
    movie = movie.scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    update_data = movie_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        if key not in ["genre_ids", "director_ids", "actor_ids", "certification_id"]:
            setattr(movie, key, value)

    if "certification_id" in update_data and update_data["certification_id"] is not None:
        cert = await db.execute(select(CertificationModel).filter_by(id=update_data["certification_id"]))
        if not cert.scalars().first():
            raise HTTPException(status_code=400, detail="Certification ID not found")
        movie.certification_id = update_data["certification_id"]

    if "genre_ids" in update_data and update_data["genre_ids"] is not None:
        genres = await db.execute(select(GenreModel).filter(GenreModel.id.in_(update_data["genre_ids"])))
        found_genres = genres.scalars().all()
        if len(found_genres) != len(update_data["genre_ids"]):
            raise HTTPException(status_code=400, detail="One or more genre IDs not found")
        movie.genres = found_genres

    if "director_ids" in update_data and update_data["director_ids"] is not None:
        directors = await db.execute(select(DirectorModel).filter(DirectorModel.id.in_(update_data["director_ids"])))
        found_directors = directors.scalars().all()
        if len(found_directors) != len(update_data["director_ids"]):
            raise HTTPException(status_code=400, detail="One or more director IDs not found")
        movie.directors = found_directors

    if "actor_ids" in update_data and update_data["actor_ids"] is not None:
        actors = await db.execute(select(ActorModel).filter(ActorModel.id.in_(update_data["actor_ids"])))
        found_actors = actors.scalars().all()
        if len(found_actors) != len(update_data["actor_ids"]):
            raise HTTPException(status_code=400, detail="One or more actor IDs not found")
        movie.actors = found_actors

    try:
        await db.commit()
        await db.refresh(movie)
        await db.refresh(movie, attribute_names=['certification', 'genres', 'directors', 'actors'])
        return movie
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not update movie: {e}")


# Delete Movie (Moderator only, with purchase check)
@router.delete("/{movie_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_movie(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> None:
    """
    Delete a movie by ID. Prevents deletion if any user has purchased it (Moderator only).
    """
    movie = await db.execute(select(MovieModel).filter_by(id=movie_id))
    movie = movie.scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    purchases_count = await db.execute(
        select(func.count(OrderItem.id)).filter_by(movie_id=movie_id)
    )
    if purchases_count.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete movie: at least one user has purchased it."
        )

    try:
        await db.delete(movie)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete movie: {e}")
    return


# --- CRUD for Genres (Moderator only) ---
@router.post("/genres", response_model=GenreCreate, status_code=status.HTTP_201_CREATED)
async def create_genre(
        genre: GenreCreate,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> GenreResponse:
    """Create a new genre (Moderator only)."""
    existing_genre = await db.execute(select(GenreModel).filter_by(name=genre.name))
    if existing_genre.scalars().first():
        raise HTTPException(status_code=409, detail="Genre with this name already exists")
    new_genre = GenreModel(name=genre.name)
    try:
        db.add(new_genre)
        await db.commit()
        await db.refresh(new_genre)
        return new_genre
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not create genre: {e}")


@router.put("/genres/{genre_id}", response_model=GenreResponse)
async def update_genre(
        genre_id: int,
        genre_update: GenreCreate,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> GenreResponse:
    """Update an existing genre (Moderator only)."""
    genre = await db.execute(select(GenreModel).filter_by(id=genre_id))
    genre = genre.scalars().first()
    if not genre:
        raise HTTPException(status_code=404, detail="Genre not found")

    # Check if new name conflicts with existing genre (excluding self)
    if genre_update.name and genre_update.name != genre.name:
        existing_genre = await db.execute(select(GenreModel).filter(
            (GenreModel.name == genre_update.name) & (GenreModel.id != genre_id)
        ))
        if existing_genre.scalars().first():
            raise HTTPException(status_code=409, detail="Genre with this name already exists")

    genre.name = genre_update.name
    try:
        await db.commit()
        await db.refresh(genre)
        return genre
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not update genre: {e}")


@router.delete("/genres/{genre_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_genre(
        genre_id: int,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> None:
    """Delete a genre (Moderator only)."""
    genre = await db.execute(select(GenreModel).filter_by(id=genre_id))
    genre_obj = genre.scalars().first()
    if not genre_obj:
        raise HTTPException(status_code=404, detail="Genre not found")

    try:
        await db.delete(genre_obj)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete genre: {e}")


# --- CRUD for Actors (Moderator only) ---
@router.post("/actors", response_model=ActorCreate, status_code=status.HTTP_201_CREATED)
async def create_actor(
        actor: ActorCreate,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> ActorResponse:
    """Create a new actor (Moderator only)."""
    existing_actor = await db.execute(select(ActorModel).filter_by(name=actor.name))
    if existing_actor.scalars().first():
        raise HTTPException(status_code=409, detail="Actor with this name already exists")
    new_actor = ActorModel(name=actor.name)
    try:
        db.add(new_actor)
        await db.commit()
        await db.refresh(new_actor)
        return new_actor
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not create actor: {e}")


@router.put("/actors/{actor_id}", response_model=ActorResponse)
async def update_actor(
        actor_id: int,
        actor_update: ActorCreate,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> ActorResponse:
    """Update an existing actor (Moderator only)."""
    actor = await db.execute(select(ActorModel).filter_by(id=actor_id))
    actor = actor.scalars().first()
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")

    if actor_update.name and actor_update.name != actor.name:
        existing_actor = await db.execute(select(ActorModel).filter(
            (ActorModel.name == actor_update.name) & (ActorModel.id != actor_id)
        ))
        if existing_actor.scalars().first():
            raise HTTPException(status_code=409, detail="Actor with this name already exists")

    actor.name = actor_update.name
    try:
        await db.commit()
        await db.refresh(actor)
        return actor
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not update actor: {e}")


@router.delete("/actors/{actor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_actor(
        actor_id: int,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> None:
    """Delete an actor (Moderator only)."""
    actor = await db.execute(select(ActorModel).filter_by(id=actor_id))
    actor = actor.scalars().first()
    if not actor:
        raise HTTPException(status_code=404, detail="Actor not found")

    try:
        await db.delete(actor)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete actor: {e}")
    return


# --- CRUD for Certifications (Moderator only) - Adding these based on import CertificationCreate
@router.post("/certifications", response_model=CertificationCreate, status_code=status.HTTP_201_CREATED)
async def create_certification(
        certification: CertificationCreate,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> CertificationResponse:
    """Create a new certification (Moderator only)."""
    existing_cert = await db.execute(select(CertificationModel).filter_by(name=certification.name))
    if existing_cert.scalars().first():
        raise HTTPException(status_code=409, detail="Certification with this name already exists")
    new_cert = CertificationModel(name=certification.name)
    try:
        db.add(new_cert)
        await db.commit()
        await db.refresh(new_cert)
        return new_cert
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not create certification: {e}")


@router.put("/certifications/{cert_id}", response_model=CertificationResponse)
async def update_certification(
        cert_id: int,
        cert_update: CertificationCreate,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> CertificationResponse:
    """Update an existing certification (Moderator only)."""
    cert = await db.execute(select(CertificationModel).filter_by(id=cert_id))
    cert = cert.scalars().first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")

    if cert_update.name and cert_update.name != cert.name:
        existing_cert = await db.execute(select(CertificationModel).filter(
            (CertificationModel.name == cert_update.name) & (CertificationModel.id != cert_id)
        ))
        if existing_cert.scalars().first():
            raise HTTPException(status_code=409, detail="Certification with this name already exists")

    cert.name = cert_update.name
    try:
        await db.commit()
        await db.refresh(cert)
        return cert
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not update certification: {e}")


@router.delete("/certifications/{cert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_certification(
        cert_id: int,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> None:
    """Delete a certification (Moderator only)."""
    cert = await db.execute(select(CertificationModel).filter_by(id=cert_id))
    cert = cert.scalars().first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certification not found")

    try:
        await db.delete(cert)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete certification: {e}")


# --- CRUD for Directors (Moderator only) ---
@router.post("/directors", response_model=DirectorCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_director(
        director: DirectorCreate,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> DirectorResponse:
    """
    Create a new director (Moderator only).
    """
    existing_director = await db.execute(select(DirectorModel).filter_by(name=director.name))
    if existing_director.scalars().first():
        raise HTTPException(status_code=409, detail="Director with this name already exists")

    new_director = DirectorModel(name=director.name)
    try:
        db.add(new_director)
        await db.commit()
        await db.refresh(new_director)
        return new_director
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not create director: {e}")


@router.get("/directors", response_model=List[DirectorResponse])
async def get_all_directors(
        db: AsyncSession = Depends(get_db),
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1, le=100)
) -> List[DirectorResponse]:
    """
    Get a list of all directors with pagination, including their movies.
    """
    query = select(DirectorModel).options(
        selectinload(DirectorModel.movies).selectinload(MovieModel.certification),
        selectinload(DirectorModel.movies).selectinload(MovieModel.genres),
        selectinload(DirectorModel.movies).selectinload(MovieModel.actors)
    )
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    directors = result.scalars().unique().all()
    return directors


@router.get("/directors/{director_id}", response_model=DirectorResponse)
async def get_director(
        director_id: int,
        db: AsyncSession = Depends(get_db)
) -> DirectorResponse:
    """
    Get information about a specific director by ID, including a list of associated movies.
    """
    query = select(DirectorModel).filter_by(id=director_id).options(
        selectinload(DirectorModel.movies).selectinload(MovieModel.certification),
        selectinload(DirectorModel.movies).selectinload(MovieModel.genres),
        selectinload(DirectorModel.movies).selectinload(MovieModel.actors)
    )
    result = await db.execute(query)
    director_obj = result.scalars().first()
    if not director_obj:
        raise HTTPException(status_code=404, detail="Director not found.")
    return director_obj


@router.put("/directors/{director_id}", response_model=DirectorResponse)
async def update_director(
        director_id: int,
        director_update: DirectorUpdate,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> DirectorResponse:
    """
    Update an existing director by ID (Moderator only).
    """
    # Fetch the director and eager-load movies if the response model expects them
    # For a PUT operation, typically only the updated fields are returned,
    # but if DirectorResponse includes movies, we need to load them.
    # If not, the initial `select` without options is fine.
    director_query = select(DirectorModel).filter_by(id=director_id).options(
        selectinload(DirectorModel.movies).selectinload(MovieModel.certification),
        selectinload(DirectorModel.movies).selectinload(MovieModel.genres),
        selectinload(DirectorModel.movies).selectinload(MovieModel.actors)
    )
    director = await db.execute(director_query)
    director_obj = director.scalars().first()

    if not director_obj:
        raise HTTPException(status_code=404, detail="Director not found.")

    if director_update.name is not None and director_update.name != director_obj.name:
        existing_director = await db.execute(select(DirectorModel).filter(
            (DirectorModel.name == director_update.name) & (DirectorModel.id != director_id)
        ))
        if existing_director.scalars().first():
            raise HTTPException(status_code=409, detail="Director with this name already exists.")
        director_obj.name = director_update.name

    try:
        await db.commit()
        await db.refresh(director_obj)
        await db.refresh(director_obj, attribute_names=['movies'])
        return director_obj
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Could not update director: {e}")


@router.delete("/directors/{director_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_director(
        director_id: int,
        db: AsyncSession = Depends(get_db),
        moderator: UserModel = Depends(get_current_moderator)
) -> None:
    """
    Delete a director by ID (Moderator only). Prevents deletion if the director is associated with existing movies.
    """
    director = await db.execute(select(DirectorModel).filter_by(id=director_id))
    director_obj = director.scalars().first()
    if not director_obj:
        raise HTTPException(status_code=404, detail="Director not found.")


    movies_count_stmt = select(func.count(MoviesDirectorsModel.c.movie_id)).filter(
        MoviesDirectorsModel.c.director_id == director_id
    )
    movies_count = await db.execute(movies_count_stmt)
    if movies_count.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete director: associated with existing movies."
        )

    try:
        await db.delete(director_obj)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Could not delete director: {e}")
