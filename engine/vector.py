from database.database_setup import Movie, User_Interaction
from uuid import UUID
from sqlmodel import select,cast,String,text    
from sqlalchemy.dialects.postgresql import JSONB
from flashrank import RerankRequest
import scripts.dependencies as d
import asyncio
import numpy as np 
from langfuse import observe

async def create_vector(prompt: list | str):
    # SentenceTransformer.encode() zwraca numpy array bezpośrednio (nie dict jak BGEM3FlagModel)
    result = await asyncio.to_thread(
        d.model.encode, prompt,
        batch_size=20,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    return result.tolist()  # type: ignore

@observe(as_type="span", name="reranker")
async def reranker(prompt, top_movies: list, limit_movies:int = 25):
    if not top_movies:
        return []

    passages = [
        {
            "id": i,
            "text": f"{m['movie'].title} | {', '.join(m['movie'].genre or [])} | {', '.join((m['movie'].tags or []))} | {(m['movie'].description or '')[:300]}"
        }
        for i, m in enumerate(top_movies)
    ]
    # reranker 
    request = RerankRequest(query=prompt, passages=passages)
    results = await asyncio.to_thread(d.reranker.rerank, request)

    reranked = [top_movies[r["id"]] for r in results[:limit_movies]] # bierzemy z top movies topowe filmy wedlug rerankera wiec jest tam poster_path etc
    return reranked

@observe(as_type="span", name="hybrid search")
async def hybrid_search(query_vector: list[float], max_runtime: int, session, user_list, allow_seen_dict: dict | None = None, hard_nos: list[str] | None = None, rating_weight: float = 0.1, limit_movies: int = 100) -> list:
    

    # HNSW ef_search — wyższy = dokładniejszy ale wolniejszy (default 40, max 1000)
    session.exec(text("SET hnsw.ef_search = 100;"))  # type: ignore

    rating_penalty = (10.0 - Movie.rating) / 10.0 
    # tym mniejszy hybrid_score tym lepiej, tym gorsza ocena tym dodatkowo "dalej" od idealnego filmu 0.0

    hybrid_score = (Movie.embedding.cosine_distance(query_vector) + (rating_weight * rating_penalty)).label("score") # type: ignore

    statement = (
        select(Movie, hybrid_score)
        .order_by(hybrid_score)
        .where(Movie.runtime <= max_runtime )
    )

    if hard_nos:
        for genre in hard_nos:
            statement = statement.where(~cast(Movie.genre, JSONB).contains([genre]))

    banned_users = []
    if allow_seen_dict:
        # szukamy UUID userów, którzy NIE pozwalają na widziane filmy
        banned_users = [UUID(str(uid)) for uid, data in allow_seen_dict.items() if not data.get("allow_seen", False)]
    else:
        # jeśli brak dict, banujemy dla wszystkich u których sprawdzamy (domyślne zachowanie)
        banned_users = [u.user_id for u in user_list] if user_list else []
        
    if banned_users:
        banned_subquery = select(User_Interaction.movie_id).where(User_Interaction.user_id.in_(banned_users))
        statement = statement.where(Movie.movie_id.notin_(banned_subquery))

    statement = statement.limit(limit_movies)
        
    return [
        {"movie": row[0], "score": float(row[1])}
        for row in session.exec(statement).all()
    ]

@observe(as_type="span", name="temperature")
async def temperature(top_movies, limit: int = 40, temp: float = 0.8):
    if not top_movies: return []

    scores = np.array([m["score"] for m in top_movies])

    # Przekształcamy dystans na miarę podobieństwa (odwracamy znak) i dzielimy przez temperaturę
    
    logits = -scores / temp
    
    # Odejmujemy max dla stabilności numerycznej exp()
    exp_logits = np.exp(logits - np.max(logits))
    probabilities = exp_logits / np.sum(exp_logits)
    probabilities /= probabilities.sum()  # Wzmocnienie stabilności numerycznej dla np.random.choice
    
    # Losujemy `limit` filmów bez powtórzeń zgodnie z wagami prawdopodobieństwa
    chosen_indices = np.random.choice(
        len(top_movies), 
        size=min(limit, len(top_movies)), 
        replace=False, 
        p=probabilities
    )
    
    return [top_movies[i] for i in chosen_indices]