from fastapi import APIRouter, HTTPException, status, Depends, Request
from sqlmodel import select
from database.main_db import get_session
from database.database_setup import User, Movie, User_Interaction
from schemas.schemas import RateRequest
from scripts.security import get_current_user
from scripts.dependencies import limiter
import numpy as np

router = APIRouter(prefix="/rating", tags=["rating"])

# wagi: LOVE/LIKE → taste_positive,  HATE/DISLIKE → taste_negative
WEIGHTS = {
    "LOVE": ("positive", 1.0),
    "LIKE": ("positive", 0.5),
    "HATE": ("negative", 1.0),
    "DISLIKE": ("negative", 0.5),
}


def _incremental_update(old_taste, count, embedding, weight):
    """new_taste = normalize(old_taste * count + embedding * weight)"""
    emb = np.array(embedding, dtype=np.float64)
    old = np.array(old_taste, dtype=np.float64) if old_taste else np.zeros_like(emb)
    acc = old * count + emb * weight
    norm = np.linalg.norm(acc)
    return (acc / norm).tolist() if norm > 0 else acc.tolist()


def _reverse_update(old_taste, count, embedding, weight):
    """Odwraca poprzedni incremental update. Zwraca (new_taste | None, new_count)."""
    if not old_taste or count <= 0:
        return None, 0
    if count == 1:
        return None, 0

    emb = np.array(embedding, dtype=np.float64)
    acc = np.array(old_taste, dtype=np.float64) * count - emb * weight
    norm = np.linalg.norm(acc)
    if norm > 0:
        return (acc / norm).tolist(), count - 1
    return None, count - 1


def _remove_old_rating(user, embedding, old_status):
    """Odwraca wpływ starego ratingu na wektor taste."""
    if old_status not in WEIGHTS:
        return
    side, weight = WEIGHTS[old_status]
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
    side, weight = WEIGHTS[new_status]
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


@router.post("/rate", summary="Rate a movie (LOVE / LIKE / DISLIKE / HATE)")
@limiter.limit("30/minute")
async def rate_movie(
    request: Request,
    data: RateRequest,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    user_id = user_token["user_id"]

    user = session.exec(select(User).where(User.user_id == user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    movie = session.exec(select(Movie).where(Movie.movie_id == data.movie_id)).first()
    if not movie or not movie.embedding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found or has no embedding")

    new_status = data.status.upper().strip()

    # sprawdź czy już istnieje interaction
    existing = session.exec(
        select(User_Interaction).where(
            User_Interaction.user_id == user_id,
            User_Interaction.movie_id == data.movie_id,
        )
    ).first()

    # odwróć stary rating jeśli był
    if existing and existing.status in WEIGHTS:
        _remove_old_rating(user, movie.embedding, existing.status)

    # zastosuj nowy rating
    _apply_new_rating(user, movie.embedding, new_status)

    # upsert interaction
    if existing:
        existing.status = new_status
    else:
        session.add(User_Interaction(user_id=user_id, movie_id=data.movie_id, status=new_status))

    session.add(user)
    session.commit()

    return {"status": new_status, "positive_count": user.positive_count, "negative_count": user.negative_count}


@router.delete("/rate", summary="Remove a movie rating")
@limiter.limit("30/minute")
async def unrate_movie(
    request: Request,
    data: RateRequest,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    user_id = user_token["user_id"]

    user = session.exec(select(User).where(User.user_id == user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    movie = session.exec(select(Movie).where(Movie.movie_id == data.movie_id)).first()
    if not movie:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movie not found")

    existing = session.exec(
        select(User_Interaction).where(
            User_Interaction.user_id == user_id,
            User_Interaction.movie_id == data.movie_id,
        )
    ).first()
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No rating found for this movie")

    # odwróć wpływ na wektor
    if existing.status in WEIGHTS and movie.embedding:
        _remove_old_rating(user, movie.embedding, existing.status)

    session.delete(existing)
    session.add(user)
    session.commit()

    return {"message": "Rating removed", "positive_count": user.positive_count, "negative_count": user.negative_count}


@router.get("/history", summary="Get user's rating history")
@limiter.limit("30/minute")
async def get_rating_history(
    request: Request,
    user_token: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    user_id = user_token["user_id"]

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
