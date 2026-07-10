
from engine.prompts import AGENT_SYSTEM_PROMPT
from engine.vector import hybrid_search, reranker
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date
import os
import time, random
import logging
from openai import AsyncOpenAI 

logger = logging.getLogger(__name__)
client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY"))
# ── Schematy dla LLM (tylko to co model może znać) ──────────────────────────

class LlmExtraMovie(BaseModel):
    """Schemat extra filmów zwracanych przez LLM — tylko tytuł i gatunki."""
    movie_title: str
    genres: list[str] = Field(default_factory=list)

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
    genres: list[str]
    poster_path: str
    release_date: Optional[date] = None   # mapowane z bazy po tytule
    runtime: Optional[int] = None
    rating: Optional[float] = None

class MovieRecommendation(BaseModel):
    thought: str
    movie_title: str
    reasoning_pl: str
    extra_movies: list[ExtraMovie] 
    poster_path: str
    genres: list[str]
    release_date: Optional[date] = None   # mapowane z bazy po tytule
    runtime: Optional[int] = None
    rating: Optional[float] = None

async def decide(session, query, runtime: int, llm_prompt: str, reranker_query: str, allow_seen_dict: dict | None = None, rating_weight: float = 0.25, limit_movies: int = 75):
    t1 = time.perf_counter()
    top_search = await hybrid_search(query, runtime, session, allow_seen_dict, rating_weight, limit_movies)
    t2 = time.perf_counter()
    logger.info(f"hybrid serach took {t2-t1}")
    rerank = await reranker(reranker_query, top_search, limit_movies=20)
    t3 = time.perf_counter()
    logger.info(f"rerank took {t3-t2}")
    
    if not rerank:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Brak filmów spełniających kryteria, spróbuj np. zwiększyć maksymalny czas trwania.")
        

    random.shuffle(rerank)
    movie_lookup = {m['movie'].title: m['movie'] for m in rerank}
    # case-insensitive lookup — LLM często zwraca tytuł z inną wielkością liter
    movie_lookup_lower = {k.lower(): v for k, v in movie_lookup.items()}

    def find_movie(title: str):
        """Szuka filmu po tytule — najpierw exact, potem case-insensitive."""
        return movie_lookup.get(title) or movie_lookup_lower.get(title.lower())
    
    movies_str = "\n".join([
        f"- {m['movie'].title} | "
        f"{', '.join(m['movie'].genre or [])} | "
        f"{', '.join(m['movie'].tags or [])} | "
        f"{m['movie'].description[:150]}"
        for m in rerank
    ])
    user_prompt = f"""
    Candidates:
    {movies_str}

    Group preferences: {llm_prompt}
    Output:
    """

    from fastapi import HTTPException
    from openai import RateLimitError, AuthenticationError, APIConnectionError, APIStatusError
    from pydantic import ValidationError

    try:
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.25,
            top_p=0.9,
            response_format={"type": "json_object"},
        )
        raw_content = response.choices[0].message.content or ""

    except RateLimitError as e:
        logger.warning(f"Groq rate limit: {e}")
        raise HTTPException(
            status_code=429,
            detail="We have problem with limit of our AI provider. Try again later."
        )
    except AuthenticationError as e:
        logger.error(f"Groq auth error: {e}")
        raise HTTPException(
            status_code=500,
            detail="We have problem with authentication of our AI provider. Try again later."
        )
    except APIConnectionError as e:
        logger.error(f"Groq connection error: {e}")
        raise HTTPException(
            status_code=503,
            detail="We have problem with connection to our AI provider. Try again later."
        )
    except APIStatusError as e:
        logger.error(f"Groq API error {e.status_code}: {e.message}")
        raise HTTPException(
            status_code=502,
            detail=f"We have problem with AI provider. Try again later."
        )

    try:
        llm_result = LlmOutput.model_validate_json(raw_content)
    except ValidationError as e:
        logger.error(f"LLM zwrócił nieprawidłowy JSON: {raw_content[:300]}\nBłąd: {e}")
        raise HTTPException(
            status_code=500,
            detail="AI zwróciło nieprawidłową odpowiedź — spróbuj ponownie."
        )

    t4 = time.perf_counter()
    logger.info(f"llm took {t4-t3:.2f}s")

    # mapujemy dane z bazy (poster, rok, gatunki, czas trwania, ocena)
    matched = find_movie(llm_result.movie_title)
    result = MovieRecommendation(
        thought=llm_result.thought,
        movie_title=llm_result.movie_title,
        reasoning_pl=llm_result.reasoning,
        extra_movies=[],
        poster_path=matched.poster_path or '' if matched else '',
        genres=matched.genre or [] if matched else llm_result.genres,
        release_date=matched.release_date if matched else None,
        runtime=matched.runtime if matched else None,
        rating=matched.rating if matched else None,
    )

    for extra in llm_result.extra_movies:
        matched_extra = find_movie(extra.movie_title)
        result.extra_movies.append(ExtraMovie(
            movie_title=extra.movie_title,
            genres=matched_extra.genre or [] if matched_extra else extra.genres,
            poster_path=matched_extra.poster_path or '' if matched_extra else '',
            release_date=matched_extra.release_date if matched_extra else None,
            runtime=matched_extra.runtime if matched_extra else None,
            rating=matched_extra.rating if matched_extra else None,
        ))

    return result
