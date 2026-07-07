from sqlmodel import Field, SQLModel, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import UniqueConstraint
from uuid import UUID, uuid4
from pgvector.sqlalchemy import Vector
from datetime import date
from pydantic import field_validator
from schemas.schemas import INTERACTION_STATUSES



class User(SQLModel, table=True):
    """
        Table for users postgresql containig:
        user_id - primary key
        email - unique
        hash_password
    """
    __tablename__ = "app_user" # type: ignore
    __table_args__ = (UniqueConstraint("email"),)
    user_id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    hash_password: str

    taste_positive: list[float] | None = Field(sa_column=Column(Vector(768)), default=None)
    taste_negative: list[float] | None = Field(sa_column=Column(Vector(768)), default=None)
    saved_preferences: dict | None = Field(default_factory=dict, sa_column=Column(JSONB))
    history: list[float] | None = Field(sa_column=Column(Vector(768), default=None))

class Movie(SQLModel, table=True):

    __tablename__= "movie" # type: ignore
    movie_id: UUID = Field(default_factory=uuid4, primary_key=True)
    tmdb_id: int = Field(unique=True, index=True)

    title: str  = Field(index=True)
    description: str | None = Field(default=None)
    genre: list[str] | None = Field(default_factory=list, sa_column=Column(JSONB))
    poster_path: str| None = Field(default=None)
    release_date: date | None = Field(default=None)
    runtime: int | None = Field(default=None, index=True)
    rating: float = Field(default=None, index=True)
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSONB))

    embedding: list[float] | None = Field(sa_column=Column(Vector(768), default=None))

class Room_Session(SQLModel,table=True):
    __tablename__ = "room_session" # type: ignore
    session_id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    is_active: bool = Field(default=True)
    recomended_runtime: int | None = Field(default=None, index=True)
    min_runtime: int | None = Field(default=None, index=True)
    occasion: str | None = Field(default=None, index=True)
    allow_seen: dict = Field(default_factory=dict, sa_column=Column(JSONB))

    preferences: list | None= Field(default_factory=list, sa_column=Column(JSONB))
    created_at: date | None = Field(default_factory=date.today)

    users_in_session: list[str] = Field(default_factory=list, sa_column=Column(JSONB))
    embedding_preferences: list[float] | None = Field(sa_column=Column(Vector(768)), default=None)
    conflict: bool= Field(default=False)


class Rating(SQLModel, table=True):

    __tablename__ = "rating" # type: ignore
    rating_id: UUID = Field(default_factory=uuid4, primary_key=True)
    
    user_id: UUID = Field(foreign_key="app_user.user_id", index=True)
    movie_id: UUID = Field(foreign_key="movie.movie_id", index=True)
    session_id: UUID = Field(foreign_key="room_session.session_id", index=True)
    
    rated_at: date | None = Field(default_factory=date.today)
    # -1 = dislike 0 = have seen no opinion 1 = like 
    rating: int = Field(default=0, index=True) 


class MovieSessionDB(SQLModel, table=True):
    """
    Tabela sesji filmowej — pełny cykl życia od lobby do rekomendacji.
    Host tworzy sesję → członkowie dołączają kodem → podają preferencje →
    host wywołuje rekomendacje → wyniki widoczne dla wszystkich.
    """
    __tablename__ = "movie_session"  # type: ignore

    session_id: UUID = Field(default_factory=uuid4, primary_key=True)
    host_id: UUID = Field(foreign_key="app_user.user_id", index=True)
    invite_code: str = Field(unique=True, index=True)

    meeting_type: str = Field(index=True)  # RANDKA / EKIPA / RODZINA / SOLO
    status: str = Field(default="LOBBY", index=True)  # LOBBY / ALL_READY / RECOMMENDING / COMPLETED

    members: list[dict] | None = Field(default_factory=list, sa_column=Column(JSONB))
    recommendations: list[dict] | None = Field(default=None, sa_column=Column(JSONB))

    room_session_id: UUID | None = Field(default=None, foreign_key="room_session.session_id")
    created_at: date | None = Field(default_factory=date.today)

class User_Interaction(SQLModel, table=True):
    __tablename__ = "user_interaction" # type: ignore
    interaction_id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="app_user.user_id", index=True)
    movie_id: UUID = Field(foreign_key="movie.movie_id", index=True)
    status: str = Field(default="NEUTRAL", index=True)  # DISLIKE / LIKE / NEUTRAL / LOVE / HATE / WATCHED

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        v = v.upper().strip()
        if v not in INTERACTION_STATUSES:
            raise ValueError(f"Invalid status '{v}'. Must be one of: {INTERACTION_STATUSES}")
        return v