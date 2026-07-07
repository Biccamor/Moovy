# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import select
from database.database_setup import Movie
from scripts.security import get_current_user
from database.main_db import get_session
from scripts.dependencies import limiter
import re


def _escape_like(value: str) -> str:
    """Escapuje znaki specjalne ILIKE (%, _, \\) żeby user nie mógł manipulować wzorcem."""
    return re.sub(r"([%_\\])", r"\\\1", value)


router = APIRouter()

@router.get("/movies/search", summary="Search for favourite movies")
@limiter.limit("30/minute")
async def search(
    request: Request,
    title: str = Query(..., min_length=1, max_length=200, description="Movie title to search for"),
    limit: int = Query(default=10, ge=1, le=50, description="Max number of results (1-50)"),
    user: dict = Depends(get_current_user),
    session = Depends(get_session),
):
    safe_title = _escape_like(title.strip())
    query = select(Movie).where(Movie.title.ilike(f"%{safe_title}%")).order_by(Movie.rating.desc()).limit(limit)
    results = session.exec(query).all()

    return [
        {
            "movie_id": movie.movie_id,
            "title": movie.title,
            "poster_path": movie.poster_path,
            "year": movie.release_date.year if movie.release_date else None,
        }
        for movie in results
    ]
