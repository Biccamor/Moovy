import numpy as np
from database.database_setup import Movie

def rrf(user_list:dict, top_movies:list, session, limit_movies: int = 15, alpha: float = 0.3):    
    
    not_taste = True
    for u in user_list:
        if u.taste_positive is not None:
            not_taste = False
            break 
    if not_taste: 
        return top_movies 
    
    embeddings = np.array([m['movie'].embedding for m in top_movies])
    
    combined = 0
    candidates = 0
    for u in user_list:

        if not u.taste_positve:
            continue 
        candidates += 1 

        score = embeddings @ u.taste_positive

        if not u.taste_negative: 
            score -= alpha*(embeddings@u.taste_negative)
        combined += score
    combined /= candidates

    ranked_movies = np.argsort(-combined)[:limit_movies]

    return [top_movies[i] for i in ranked_movies]
        