# pyrefly: ignore [missing-import]
from fastapi.routing import APIRouter
from database.database_setup import User, User_Interaction
from .auth_router import get_user
from main import app
from fastapi import Depends

router = APIRouter()
