from typing import Self, List, Literal, Optional

from pydantic import BaseModel, Field, EmailStr, model_validator, field_validator
from uuid import uuid4, UUID
from pydantic_settings import BaseSettings, SettingsConfigDict

VibeType = Literal["EXISTENTIAL", "MIND_BENDER", "ADRENALINE", "DATE_NIGHT", "DEEP_FEELS", "LAUGH_RIOT", "SPINE_CHILLING", 
                   "FAMILY_FUN", "HISTORY_LESSON", "EPIC_JOURNEY", "GUILTY_PLEASURE"]

INTERACTION_STATUSES: list[str] = ["LIKE", "DISLIKE", "LOVE", "NEUTRAL", "HATE", "WATCHED", "WATCHLIST"]

class RateRequest(BaseModel):
    """Request body for rating a movie."""
    movie_id: UUID | str | int
    status: str

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: str) -> str:
        if isinstance(v, str):
            v = v.upper().strip()
        if v not in INTERACTION_STATUSES:
            raise ValueError(f"Invalid status '{v}'. Must be one of: {INTERACTION_STATUSES}")
        return v


class Preferences(BaseModel): #podawane przy nowym requescie/sesji
    vibes: List[VibeType] = Field(default_factory=list, max_length=12)
    hard_nos: List[str] = Field(default_factory=list, max_length=12)
    max_runtime: int = Field(default=120, ge=30, le=240)
    allow_seen: bool = False
    eras: List[str] = Field(default_factory=list, max_length=10)

class SavedPreferences(BaseModel): #jednorazowo podane przy rejestracji
    vibes: List[VibeType] = Field(default_factory=list)
    hard_nos: List[str] = Field(default_factory=list)
    eras: List[str] = Field(default_factory=list)
    movies: List[str] = Field(default_factory=list)

class User(BaseModel):
    email: EmailStr #haslo jest przywiazane do maila nie usera
    user_id: UUID
    user_name: str
    saved_preferences: SavedPreferences
    profile_picture: Optional[str] = None #zgnieciony obrazek do profilu

class MovieRequest(BaseModel): #pojedynczy request o film niekoniecznie z sesji
    user_id: UUID
    final_preferences: Preferences

class MovieSessionUser(BaseModel): #czlonek sesji
    user_id: UUID
    user_name: str = Field(max_length=50)
    personal_vibe: Preferences

class GhostUser(BaseModel): #czlonek sesji ktory nie jest zalogowany (coming soon)
    user_name: str
    personal_vibe: Preferences

class MovieSession(BaseModel): #sesja od jednego uzytkownika do ktorej dolaczyc moze wiecej
    host_id: UUID
    session_id: UUID = Field(default_factory=uuid4)
    invite_code: str  # Np. "XJ79B" - do wejścia przez kod/QR
    
    meeting_type: Literal["RANDKA", "EKIPA", "RODZINA", "SOLO"]
    
    is_active: bool = True
    users: List[MovieSessionUser] = Field(default_factory=list)
    
    final_preferences: Optional[Preferences] = None

class Register(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, title="Your password must have at least 8 characters", max_length=100)
    confirm_password: str

    @model_validator(mode="after")
    def password_match(self) -> Self:
        if self.password == self.confirm_password:
            return self
    
        raise ValueError("Passwords don't match")

class Login(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, title="Enter your password")

class RefreshRequest(BaseModel):
    refresh_token: str

class AppSettings(BaseModel):
    theme: Literal["DARK", "LIGHT", "SYSTEM"] = "LIGHT"

class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str
    access_token_expire: int = 60          # minuty (domyślnie 60 min)
    refresh_token_expire_days: int = 14     # dni (domyślnie 14 dni / 2 tygodnie)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# ─── Sesja filmowa ───────────────────────────────────────────────────

MeetingType = Literal["RANDKA", "EKIPA", "RODZINA", "SOLO"]
MemberStatus = Literal["pending", "ready"]

class CreateSessionRequest(BaseModel):
    """Request od hosta — tworzy nową sesję."""
    meeting_type: MeetingType

class JoinSessionRequest(BaseModel):
    """Request od członka — dołącza do sesji kodem zaproszenia."""
    invite_code: str = Field(min_length=1, max_length=10)

class MemberPreferencesRequest(BaseModel):
    """Request od członka — podaje swoje preferencje na tę sesję."""
    preferences: Preferences

class SessionMemberResponse(BaseModel):
    """Widok członka sesji w odpowiedzi API."""
    user_id: UUID
    user_name: str
    status: MemberStatus
    preferences: Optional[Preferences] = None

class SessionResponse(BaseModel):
    """Pełny widok sesji — dla hosta i członków."""
    session_id: UUID
    host_id: UUID
    invite_code: str
    meeting_type: MeetingType
    status: str  # LOBBY / ALL_READY / RECOMMENDING / COMPLETED
    members: List[SessionMemberResponse]
    recommendations: Optional[List[dict]] = None
    created_at: Optional[str] = None


# ─── Profil użytkownika ──────────────────────────────────────────────

class NicknameUpdate(BaseModel):
    """Request body – ustawienie / zmiana nickname'u."""
    nickname: str = Field(min_length=1, max_length=30)

class ProfilePictureUpdate(BaseModel):
    """Request body – ustawienie / zmiana zdjęcia profilowego (base64)."""
    profile_picture: str = Field(
        min_length=1,
        max_length=5_000_000,  # ~3.75 MB after base64 encoding
        description="Base64-encoded image (png/jpg/webp)",
    )

class ProfileResponse(BaseModel):
    """Publiczny widok profilu użytkownika."""
    user_id: UUID
    email: str
    nickname: Optional[str] = None
    profile_picture: Optional[str] = None
