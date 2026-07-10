from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import select
from database.database_setup import Movie, User
from scripts.security import get_current_user
from database.main_db import get_session
from scripts.dependencies import limiter


router = APIRouter(prefix="/watchlist", tags=["/watchlist"])

@router.post("/add_to_watchlist", summary="add movie to list")
@limiter.limit("30/minute")
async def add_movie(requst: Request, movie_data: Movie, user=Depends(get_current_user), session=Depends(get_session)):
