from fastapi import APIRouter, HTTPException, status, Depends, Request
from schemas.schemas import NicknameUpdate, ProfilePictureUpdate, ProfileResponse
from scripts.security import get_current_user
from database.main_db import get_session
from database.database_setup import User
from scripts.dependencies import limiter
from uuid import UUID
import base64
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])


# ─── helpers ─────────────────────────────────────────────────────────

def _get_user_or_404(user_id: str, session) -> User:
    """Pobiera użytkownika z bazy albo rzuca 404."""
    user = session.get(User, UUID(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


def _validate_base64(data: str) -> None:
    """Sprawdza czy string jest poprawnym base64."""
    try:
        # Usuń opcjonalny prefix data-URI (np. "data:image/png;base64,...")
        if "," in data:
            data = data.split(",", 1)[1]
        base64.b64decode(data, validate=True)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid base64 encoding",
        )


# ─── GET  /profile/me ───────────────────────────────────────────────

@router.get("/me", response_model=ProfileResponse)
@limiter.limit("30/minute")
async def get_my_profile(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    """Zwraca profil zalogowanego użytkownika."""
    user = _get_user_or_404(current_user["user_id"], session)
    return ProfileResponse(
        user_id=user.user_id,
        email=user.email,
        nickname=user.nickname,
        profile_picture=user.profile_picture,
    )


# ─── PUT  /profile/nickname ─────────────────────────────────────────

@router.put("/nickname")
@limiter.limit("10/minute")
async def update_nickname(
    request: Request,
    data: NicknameUpdate,
    current_user: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    """Ustawia lub zmienia nickname użytkownika."""
    user = _get_user_or_404(current_user["user_id"], session)
    user.nickname = data.nickname
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"message": "Nickname updated", "nickname": user.nickname}


# ─── PUT  /profile/picture ──────────────────────────────────────────

@router.put("/picture")
@limiter.limit("5/minute")
async def update_profile_picture(
    request: Request,
    data: ProfilePictureUpdate,
    current_user: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    """Ustawia lub zmienia zdjęcie profilowe (base64-encoded)."""
    _validate_base64(data.profile_picture)
    user = _get_user_or_404(current_user["user_id"], session)
    user.profile_picture = data.profile_picture
    session.add(user)
    session.commit()
    session.refresh(user)
    return {"message": "Profile picture updated"}


# ─── DELETE  /profile/picture ────────────────────────────────────────

@router.delete("/picture")
@limiter.limit("5/minute")
async def delete_profile_picture(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session=Depends(get_session),
):
    """Usuwa zdjęcie profilowe."""
    user = _get_user_or_404(current_user["user_id"], session)
    user.profile_picture = None
    session.add(user)
    session.commit()
    return {"message": "Profile picture removed"}
