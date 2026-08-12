# pyrefly: ignore [missing-import]
import os
import re
import requests
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlmodel import select
from database.database_setup import Movie, User_Interaction, User
from scripts.security import get_current_user
from database.main_db import get_session
from scripts.dependencies import limiter


def _escape_like(value: str) -> str:
    """Escapuje znaki specjalne ILIKE (%, _, \\) żeby user nie mógł manipulować wzorcem."""
    return re.sub(r"([%_\\])", r"\\\1", value)


def _find_movie(session, movie_id_arg) -> Movie | None:
    """Szuka filmu po movie_id (UUID) lub tmdb_id (int/string)."""
    if movie_id_arg is None:
        return None

    if isinstance(movie_id_arg, UUID):
        return session.exec(select(Movie).where(Movie.movie_id == movie_id_arg)).first()
    
    val_str = str(movie_id_arg).strip()
    try:
        val_uuid = UUID(val_str)
        movie = session.exec(select(Movie).where(Movie.movie_id == val_uuid)).first()
        if movie:
            return movie
    except ValueError:
        pass

    try:
        tmdb_val = int(val_str)
        return session.exec(select(Movie).where(Movie.tmdb_id == tmdb_val)).first()
    except ValueError:
        pass

    return None


router = APIRouter(prefix="/movies", tags=["/movies"])

@router.get("/search", summary="Search for favourite movies")
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


@router.get("/{movie_identifier}/providers", summary="Get streaming providers for a movie from TMDB")
@limiter.limit("60/minute")
async def get_movie_providers(
    request: Request,
    movie_identifier: str,
    user: dict = Depends(get_current_user),
    session = Depends(get_session),
):
    tmdb_id = None
    movie = _find_movie(session, movie_identifier)
    if movie:
        tmdb_id = movie.tmdb_id
    else:
        try:
            tmdb_id = int(movie_identifier)
        except ValueError:
            raise HTTPException(status_code=404, detail="Movie not found")

    bearer_token = os.getenv("BEARER_TOKEN")
    tmdb_api_key = os.getenv("TMDB_API")

    headers = {"accept": "application/json"}
    params = {}
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    elif tmdb_api_key:
        params["api_key"] = tmdb_api_key

    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/watch/providers"

    try:
        res = requests.get(url, headers=headers, params=params, timeout=8)
        if res.status_code == 200:
            data = res.json()
            results = data.get("results", {})
            region_data = results.get("PL") or results.get("US") or {}

            def format_providers(prov_list):
                if not prov_list:
                    return []
                return [
                    {
                        "provider_id": p.get("provider_id"),
                        "provider_name": p.get("provider_name"),
                        "logo_path": p.get("logo_path"),
                    }
                    for p in prov_list
                ]

            return {
                "tmdb_id": tmdb_id,
                "link": region_data.get("link"),
                "flatrate": format_providers(region_data.get("flatrate")),
                "rent": format_providers(region_data.get("rent")),
                "buy": format_providers(region_data.get("buy")),
                "free": format_providers(region_data.get("free")),
            }
        else:
            return {
                "tmdb_id": tmdb_id,
                "link": None,
                "flatrate": [],
                "rent": [],
                "buy": [],
                "free": [],
            }
    except Exception as e:
        return {
            "tmdb_id": tmdb_id,
            "link": None,
            "flatrate": [],
            "rent": [],
            "buy": [],
            "free": [],
            "error": str(e)
        }

