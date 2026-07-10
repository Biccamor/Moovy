from fastapi import APIRouter, HTTPException, status, Depends, Request
from schemas.schemas import SavedPreferences
from scripts.security import get_current_user
from sqlmodel import select
from database.main_db import get_session
from database.database_setup import User, Movie
from uuid import UUID
from scripts.dependencies import limiter
import numpy as np 

router = APIRouter(prefix="/preferences", tags=['preferences'])


@router.post("/save", summary="Save the basic preferences of user for movies")
@limiter.limit("10/minute")  # zapis preferencji — umiarkowany limit
async def save_preferences(request: Request, data: SavedPreferences, user_id: UUID, user_token: dict = Depends(get_current_user), session = Depends(get_session)):
    
    if str(user_id) != str(user_token["user_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nie możesz modyfikować preferencji innego użytkownika"
        )

    user = session.exec(select(User).where(User.user_id == user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    user.saved_preferences = data.model_dump()
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"message": "Preferences saved successfully", "user_id": user.user_id}


@router.get("/get", summary="Get preferences of user")
@limiter.limit("30/minute")  # odczyt — wyższy limit
async def get_preferences(request: Request, user_id: UUID, user_token: dict = Depends(get_current_user), session = Depends(get_session)):

    if str(user_id) != str(user_token["user_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nie możesz odczytywać preferencji innego użytkownika"
        )

    user = session.exec(select(User).where(User.user_id == user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user.saved_preferences or {}

@router.post("/favourite", summary="Add favourite movies to db")
@limiter.limit("1/minute")
async def add_favourites(request: Request, favourites_id: list[int], user_id: UUID, user_token: dict = Depends(get_current_user), session = Depends(get_session)):

    if len(favourites_id) > 5: 
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="You can't add more than 5 favourites"
        )

    if str(user_id) != str(user_token["user_id"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can't change other user"
        )

    user = session.exec(select(User).where(User.user_id == user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user_positive_vector = user.taste_positive

    for tmdb_id in favourites_id: 

        movie = session.exec(select(Movie).where(tmdb_id==Movie.tmdb_id)).first()

        if not movie: 
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Movie not found" 
            )

        vector = movie.embedding 
        if not vector: 
            continue 

        if user_positive_vector is None: 
            user_positive_vector = vector
            continue

        user_positive_vector = np.add(user_positive_vector, vector) 
    
    if user_positive_vector is not None:
        arr = np.array(user_positive_vector)
        norm = np.linalg.norm(arr)
        if norm > 0:
            user.taste_positive = (arr / norm).tolist()    
    
    session.add(user)
    session.commit()
    session.refresh(user)
    
    return {"message": "Favourites saved", "user_id": user.user_id}

