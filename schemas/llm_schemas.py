from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
from uuid import UUID

class LlmExtraMovie(BaseModel):
    """Schemat extra filmów zwracanych przez LLM — tytuł, gatunki i reasoning."""
    movie_title: str
    genres: list[str] = Field(default_factory=list)
    reasoning: str = ""

class LlmOutput(BaseModel):
    """Schemat odpowiedzi LLM — bez poster_path i release_date (LLM ich nie zna)."""
    thought: str = ""
    movie_title: str
    reasoning: str = Field(..., description="Description of reasoning in English")
    extra_movies: list[LlmExtraMovie] =  Field(..., description="EXACTLY TWO alternate movies", min_length= 2, max_length=2)
    genres: list[str] = Field(default_factory=list)

# ── Schematy odpowiedzi API (z danymi z bazy) ────────────────────────────────

class ExtraMovie(BaseModel):
    movie_title: str
    movie_id: Optional[UUID] = None       # wewnętrzne UUID z bazy (do /rating/rate)
    genres: list[str]
    poster_path: str
    release_date: Optional[date] = None   # mapowane z bazy po tytule
    runtime: Optional[int] = None
    rating: Optional[float] = None
    tmdb_id: Optional[int] = None
    thought: str = ""

class MovieRecommendation(BaseModel):
    thought: str
    movie_title: str
    movie_id: Optional[UUID] = None       # wewnętrzne UUID z bazy (do /rating/rate)
    reasoning_pl: str
    extra_movies: list[ExtraMovie]
    poster_path: str
    genres: list[str]
    release_date: Optional[date] = None   # mapowane z bazy po tytule
    runtime: Optional[int] = None
    rating: Optional[float] = None
    tmdb_id: Optional[int] = None