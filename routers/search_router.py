# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Request
from database.database_setup import User, Movie
from main import app
from fastapi import Depends
from scripts.security import get_current_user

router = APIRouter()

@router.get("/movies/search")
async def search(request: Request, user: dict = Depends(get_current_user)):
    