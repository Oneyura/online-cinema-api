# routes/movie.py
import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import List, Optional, Union, Literal
from uuid import UUID

from sqlalchemy.orm import relationship, selectinload

from src.config.dependencies import get_db
from src.database.models.movies import (
    MovieModel,
    GenreModel,
    DirectorModel,
    ActorModel,
    CertificationModel,
    MoviesGenresModel,
    MoviesDirectorsModel,
    MoviesActorsModel
)
# Оновлено: Імпортуємо Order та OrderItem з src.database.models.orders
from src.database.models.orders import Order, OrderItem
from src.database.models.movies import (
    CommentModel,
    MovieLikeModel,
    MovieRatingModel,
    FavoriteMovieModel,
    UserModel
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
    DirectorCreate, # Додано для CRUD операцій
    CertificationCreate, # Додано для CRUD операцій
)
from src.schemas.movies import (
    CommentCreate,
    CommentResponse,
    MovieLikeCreate,
    MovieLikeResponse,
    MovieRatingCreate,
    MovieRatingResponse,
    FavoriteMovieCreate,
    FavoriteMovieResponse
)
from config.dependencies import get_current_user, get_current_moderator  # Auth dependencies

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
    # Check if movie exists
    movie = await db.execute(select(MovieModel).filter_by(id=movie_id))
    if not movie.scalars().first():
        raise HTTPException(status_code=404, detail="Movie not found")

    # Check for existing like/dislike
    existing_like = await db.execute(
        select(MovieLikeModel).filter_by(user_id=current_user.id, movie_id=movie_id) # Використовуємо current_user.id
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
        existing_like.created_at = datetime.datetime.now()  # Update timestamp
        db.add(existing_like)
        await db.commit()
        await db.refresh(existing_like)
        return existing_like
    else:
        # Create new like/dislike
        new_like = MovieLikeModel(
            user_id=current_user.id, # Використовуємо current_user.id
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
    Write a comment on a movie.
    """
    # Check if movie exists
    movie_exists = await db.execute(select(MovieModel.id).filter_by(id=movie_id))
    if not movie_exists.scalars().first():
        raise HTTPException(status_code=404, detail="Movie not found")

    new_comment = CommentModel(
        user_id=current_user.id, # Використовуємо current_user.id
        movie_id=movie_id,
        text=comment.text
    )
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)

    # Populate user for response
    await db.refresh(new_comment, attribute_names=['user'])
    return new_comment


@router.get("/{movie_id}/comments", response_model=List[CommentResponse])
async def get_movie_comments(
        movie_id: int,
        db: AsyncSession = Depends(get_db),
        page: int = Query(1, ge=1),
        limit: int = Query(10, ge=1, le=100)
) -> List[CommentResponse]:
    """
    Get all comments for a specific movie.
    """
    query = select(CommentModel).filter(CommentModel.movie_id == movie_id)

    query = query.order_by(CommentModel.created_at.desc())

    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # Eager load user for comments
    query = query.options(selectinload(CommentModel.user))

    result = await db.execute(query)
    comments = result.scalars().all()
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
        select(FavoriteMovieModel).filter_by(user_id=current_user.id, movie_id=movie_id) # Використовуємо current_user.id
    )
    if existing_favorite.scalars().first():
        raise HTTPException(status_code=409, detail="Movie already in favorites")

    new_favorite = FavoriteMovieModel(user_id=current_user.id, movie_id=movie_id) # Використовуємо current_user.id
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
        select(FavoriteMovieModel).filter_by(user_id=current_user.id, movie_id=movie_id) # Використовуємо current_user.id
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
    # Start with a query to fetch favorite movies for the current user
    # Join with MovieModel to enable filtering/sorting on movie attributes
    query = select(MovieModel).join(FavoriteMovieModel).filter(
        FavoriteMovieModel.user_id == current_user.id # Використовуємо current_user.id
    )

    # Apply filters and sorting using the helper function
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
    # Perform a LEFT JOIN with movies and group by genre to count movies
    # This part of the query is for counting, but the response_model expects nested movies
    # For now, if GenreResponse includes 'movies', Pydantic will load them.
    # If you need just the count, a custom schema or manual mapping is better.
    # The current implementation eager loads the `movies` relationship in the response.
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

    # Check for existing rating by this user for this movie
    existing_rating = await db.execute(
        select(MovieRatingModel).filter_by(user_id=current_user.id, movie_id=movie_id) # Використовуємо current_user.id
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
) -> MovieResponse:
    """
    Create a new movie (Moderator only).
    """
    # Check if certification_id exists
    cert = await db.execute(select(CertificationModel).filter_by(id=movie.certification_id))
    if not cert.scalars().first():
        raise HTTPException(status_code=400, detail="Certification ID not found")

    # Create movie instance
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

    # Handle many-to-many relationships
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

    if movie.star_ids:
        actors = await db.execute(select(ActorModel).filter(ActorModel.id.in_(movie.star_ids)))
        found_actors = actors.scalars().all()
        if len(found_actors) != len(movie.star_ids):
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
) -> MovieResponse:
    """
    Update an existing movie by ID (Moderator only).
    """
    movie = await db.execute(select(MovieModel).filter_by(id=movie_id))
    movie = movie.scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    update_data = movie_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        if key not in ["genre_ids", "director_ids", "star_ids", "certification_id"]:
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

    if "star_ids" in update_data and update_data["star_ids"] is not None:
        actors = await db.execute(select(ActorModel).filter(ActorModel.id.in_(update_data["star_ids"])))
        found_actors = actors.scalars().all()
        if len(found_actors) != len(update_data["star_ids"]):
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

    # Оновлено: Перевірка на наявність замовлень за допомогою OrderItem
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
@router.post("/genres", response_model=GenreResponse, status_code=status.HTTP_201_CREATED)
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
        genre_update: GenreCreate,  # Re-use Create schema for update fields
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
@router.post("/actors", response_model=ActorResponse, status_code=status.HTTP_201_CREATED)
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
@router.post("/certifications", response_model=CertificationResponse, status_code=status.HTTP_201_CREATED)
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