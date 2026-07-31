from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlmodel import select
from database.main_db import get_session
from database.database_setup import User, Movie, User_Interaction
from schemas.schemas import RateRequest
from scripts.security import get_current_user
from scripts.dependencies import limiter
import numpy as np
from uuid import UUID
from typing import Optional, Any

router = APIRouter(prefix="/rating", tags=["rating"])

# wagi: LOVE/LIKE → taste_positive,  HATE/DISLIKE → taste_negative
WEIGHTS = {
    "LOVE": ("positive", 1.0),
    "LIKE": ("positive", 0.5),
    "HATE": ("negative", 1.0),
    "DISLIKE": ("negative", 0.5),
    "WATCHLIST": ("neutral", 0.0),
    "WATCHED": ("neutral", 0.0),
    "NEUTRAL": ("neutral", 0.0),
}


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


def _to_numpy(value) -> np.ndarray:
    """Bezpiecznie konwertuje listę, numpy array lub JSON string na np.ndarray."""
    if isinstance(value, np.ndarray):
        return value.astype(np.float64)
    return np.array(value, dtype=np.float64)


def _incremental_update(old_taste, count, embedding, weight):
    """new_taste = normalize(old_taste * count + embedding * weight)"""
    emb = _to_numpy(embedding)
    old = _to_numpy(old_taste) if old_taste is not None and len(old_taste) > 0 else np.zeros_like(emb)
    acc = old * count + emb * weight
    norm = np.linalg.norm(acc)
    return (acc / norm).tolist() if norm > 0 else acc.tolist()


def _reverse_update(old_taste, count, embedding, weight):
    """Odwraca poprzedni incremental update. Zwraca (new_taste | None, new_count)."""
    if old_taste is None or count <= 0:
        return None, 0
    if count == 1:
        return None, 0

    emb = _to_numpy(embedding)
    acc = _to_numpy(old_taste) * count - emb * weight
    norm = np.linalg.norm(acc)
    if norm > 0:
        return (acc / norm).tolist(), count - 1
    return None, count - 1


def _remove_old_rating(user, embedding, old_status):
    """Odwraca wpływ starego ratingu na wektor taste."""
    if old_status not in WEIGHTS:
        return
    side, weight = WEIGHTS[old_status]
    if side == "neutral":
        return
        
    if side == "positive":
        user.taste_positive, user.positive_count = _reverse_update(
            user.taste_positive, user.positive_count, embedding, weight
        )
    else:
        user.taste_negative, user.negative_count = _reverse_update(
            user.taste_negative, user.negative_count, embedding, weight
        )


def _apply_new_rating(user, embedding, new_status):
    """Dodaje wpływ nowego ratingu na wektor taste."""
    if new_status not in WEIGHTS:
        return
        
    side, weight = WEIGHTS[new_status]
    if side == "neutral":
        return
        
    if side == "positive":
        user.taste_positive = _incremental_update(
            user.taste_positive, user.positive_count, embedding, weight
        )
        user.positive_count += 1
    else:
        user.taste_negative = _incremental_update(
            user.taste_negative, user.negative_count, embedding, weight
        )
        user.negative_count += 1


def _execute_rate(session, user_token: dict, movie_id_arg: Any, status_str: str) -> dict:
    user_id_raw = user_token["user_id"]
    user_id = UUID(str(user_id_raw)) if not isinstance(user_id_raw, UUID) else user_id_raw

    user = session.exec(select(User).where(User.user_id == user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if movie_id_arg is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing movie_id")

    movie = _find_movie(session, movie_id_arg)
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    new_status = status_str.upper().strip()

    existing = session.exec(
        select(User_Interaction).where(
            User_Interaction.user_id == user_id,
            User_Interaction.movie_id == movie.movie_id,
        )
    ).first()

    if movie.embedding and len(movie.embedding) > 0:
        if existing and existing.status in WEIGHTS:
            _remove_old_rating(user, movie.embedding, existing.status)
        _apply_new_rating(user, movie.embedding, new_status)

    if existing:
        existing.status = new_status
    else:
        session.add(User_Interaction(user_id=user_id, movie_id=movie.movie_id, status=new_status))

    session.add(user)
    session.commit()

    return {"status": new_status, "positive_count": user.positive_count, "negative_count": user.negative_count}


def _execute_unrate(session, user_token: dict, movie_id_arg: Any) -> dict:
    user_id_raw = user_token["user_id"]
    user_id = UUID(str(user_id_raw)) if not isinstance(user_id_raw, UUID) else user_id_raw

    user = session.exec(select(User).where(User.user_id == user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if movie_id_arg is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Missing movie_id")

    movie = _find_movie(session, movie_id_arg)
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    existing = session.exec(
        select(User_Interaction).where(
            User_Interaction.user_id == user_id,
            User_Interaction.movie_id == movie.movie_id,
        )
    ).first()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No rating found for this movie")

    if existing.status in WEIGHTS and movie.embedding and len(movie.embedding) > 0:
        _remove_old_rating(user, movie.embedding, existing.status)

    session.delete(existing)
    session.add(user)
    session.commit()

    return {"message": "Rating removed", "positive_count": user.positive_count, "negative_count": user.negative_count}


# ─── Endpointy POST rate & warianty ─────────────────────────────────

@router.post("/rate", summary="Rate a movie")
@limiter.limit("30/minute")
async def rate_movie(
    request: Request,
    data: RateRequest,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    return _execute_rate(session, user_token, data.movie_id, data.status or "LIKE")


@router.post("/rate/{target_movie_id}", summary="Rate a movie by path ID")
@limiter.limit("30/minute")
async def rate_movie_by_path(
    request: Request,
    target_movie_id: str,
    data: Optional[RateRequest] = None,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    status_str = data.status if (data and data.status) else "LIKE"
    return _execute_rate(session, user_token, target_movie_id, status_str)


@router.post("/rate/{target_movie_id}/{target_status}", summary="Rate a movie by path ID and status")
@limiter.limit("30/minute")
async def rate_movie_by_path_status(
    request: Request,
    target_movie_id: str,
    target_status: str,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    return _execute_rate(session, user_token, target_movie_id, target_status)


@router.post("/watchlist", summary="Add movie to watchlist")
@limiter.limit("30/minute")
async def add_watchlist(
    request: Request,
    data: Optional[RateRequest] = None,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    movie_id = data.movie_id if data else None
    return _execute_rate(session, user_token, movie_id, "WATCHLIST")


@router.post("/watchlist/{target_movie_id}", summary="Add movie to watchlist by path ID")
@limiter.limit("30/minute")
async def add_watchlist_by_path(
    request: Request,
    target_movie_id: str,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    return _execute_rate(session, user_token, target_movie_id, "WATCHLIST")


@router.delete("/watchlist/{target_movie_id}", summary="Remove movie from watchlist by path ID")
@limiter.limit("30/minute")
async def delete_watchlist_by_path(
    request: Request,
    target_movie_id: str,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    return _execute_unrate(session, user_token, target_movie_id)


# Shortcut endpoints for specific actions by ID
@router.post("/like/{target_movie_id}", summary="Like a movie")
@limiter.limit("30/minute")
async def like_movie_path(request: Request, target_movie_id: str, user_token: dict = Depends(get_current_user), session=Depends(get_session)):
    return _execute_rate(session, user_token, target_movie_id, "LIKE")

@router.post("/dislike/{target_movie_id}", summary="Dislike a movie")
@limiter.limit("30/minute")
async def dislike_movie_path(request: Request, target_movie_id: str, user_token: dict = Depends(get_current_user), session=Depends(get_session)):
    return _execute_rate(session, user_token, target_movie_id, "DISLIKE")

@router.post("/love/{target_movie_id}", summary="Love a movie")
@limiter.limit("30/minute")
async def love_movie_path(request: Request, target_movie_id: str, user_token: dict = Depends(get_current_user), session=Depends(get_session)):
    return _execute_rate(session, user_token, target_movie_id, "LOVE")

@router.post("/hate/{target_movie_id}", summary="Hate a movie")
@limiter.limit("30/minute")
async def hate_movie_path(request: Request, target_movie_id: str, user_token: dict = Depends(get_current_user), session=Depends(get_session)):
    return _execute_rate(session, user_token, target_movie_id, "HATE")


# ─── Endpointy DELETE rate & warianty ───────────────────────────────

@router.delete("/rate", summary="Remove a movie rating")
@limiter.limit("30/minute")
async def unrate_movie(
    request: Request,
    data: RateRequest,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    return _execute_unrate(session, user_token, data.movie_id)


@router.delete("/rate/{target_movie_id}", summary="Remove a movie rating by path ID")
@limiter.limit("30/minute")
async def unrate_movie_by_path(
    request: Request,
    target_movie_id: str,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    return _execute_unrate(session, user_token, target_movie_id)


@router.post("/delete", summary="Remove a movie rating (POST alternative)")
@router.delete("/delete", summary="Remove a movie rating")
@limiter.limit("30/minute")
async def delete_rating(
    request: Request,
    data: RateRequest,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    return _execute_unrate(session, user_token, data.movie_id)


# ─── Endpointy GET ──────────────────────────────────────────────────

@router.get("/history", summary="Get user's rating history")
@limiter.limit("30/minute")
async def get_rating_history(
    request: Request,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    user_id_raw = user_token["user_id"]
    user_id = UUID(str(user_id_raw)) if not isinstance(user_id_raw, UUID) else user_id_raw

    results = session.exec(
        select(User_Interaction, Movie)
        .join(Movie, User_Interaction.movie_id == Movie.movie_id)
        .where(User_Interaction.user_id == user_id)
    ).all()

    return [
        {
            "movie_id": str(interaction.movie_id),
            "title": movie.title,
            "poster_path": movie.poster_path,
            "status": interaction.status,
        }
        for interaction, movie in results
    ]

@router.get("/watchlist", summary="Get user's watchlist")
@limiter.limit("30/minute")
async def get_watchlist(
    request: Request,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    user_id_raw = user_token["user_id"]
    user_id = UUID(str(user_id_raw)) if not isinstance(user_id_raw, UUID) else user_id_raw

    results = session.exec(
        select(User_Interaction, Movie)
        .join(Movie, User_Interaction.movie_id == Movie.movie_id)
        .where(
            User_Interaction.user_id == user_id,
            User_Interaction.status == "WATCHLIST"
        )
    ).all()

    return [
        {
            "movie_id": str(interaction.movie_id),
            "title": movie.title,
            "poster_path": movie.poster_path,
            "runtime": movie.runtime,
            "genre": movie.genre,
            "release_date": movie.release_date
        }
        for interaction, movie in results
    ]
