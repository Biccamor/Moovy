from engine.prompts import AGENT_SYSTEM_PROMPT
from engine.vector import hybrid_search, reranker
import os
import time, random
import logging
from openai import AsyncOpenAI 
from engine.taste_reranker import fusion_ranker
from fastapi import HTTPException
from openai import RateLimitError, AuthenticationError, APIConnectionError, APIStatusError
from pydantic import ValidationError
from schemas.llm_schemas import ExtraMovie, LlmExtraMovie, LlmOutput, MovieRecommendation 
from langfuse import observe  # type: ignore[attr-defined]
from langfuse.decorators import langfuse_context  # type: ignore[import-unresolved]

logger = logging.getLogger(__name__)
client = AsyncOpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY"))

@observe(as_type="generation", name="llm-decider")
async def llm_call(user_prompt):
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

    langfuse_context.update_current_observation(
        model="llama-3.1-8b-instant",
        input=user_prompt,
        output=response.choices[0].message.content,
        usage={
            "input": response.usage.prompt_tokens,
            "output": response.usage.completion_tokens,
            "total": response.usage.total_tokens,
        } if response.usage else None,
    )

    return response


async def decide(session, query, runtime: int, llm_prompt: str, reranker_query: str, user_list, allow_seen_dict: dict | None = None, hard_nos: list[str] | None = None, rating_weight: float = 0.25, limit_movies: int = 75):
    top_search = await hybrid_search(query, runtime, session, user_list, allow_seen_dict, hard_nos, rating_weight, limit_movies)
    rerank = await reranker(reranker_query, top_search, limit_movies=35)
    taste_ranked = fusion_ranker(user_list, rerank, limit_movies=15, alpha=0.3)

    if not taste_ranked:
        raise HTTPException(status_code=404, detail="Brak filmów spełniających kryteria, spróbuj np. zwiększyć maksymalny czas trwania.")
        

    random.shuffle(taste_ranked)
    movie_lookup = {m['movie'].title: m['movie'] for m in taste_ranked}
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
        for m in taste_ranked
    ])

    user_prompt = f"""
    Candidates:
    {movies_str}

    Group preferences: {llm_prompt}
    Output:
    """


    try:
        response = await llm_call(user_prompt=user_prompt)
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
        tmdb_id=matched.tmdb_id if matched else None,
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
            tmdb_id=matched_extra.tmdb_id if matched_extra else None,
            thought=extra.reasoning,
        ))

    return result
