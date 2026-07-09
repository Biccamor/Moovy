import numpy as np

def fusion_ranker(user_list: list, top_movies: list, limit_movies: int = 15, alpha: float = 0.3):    
    
    if not top_movies:
        return []

    not_taste = True
    for u in user_list:
        if u.taste_positive is not None:
            not_taste = False
            break
    if not_taste:
        return top_movies
    
    embeddings = np.array([m['movie'].embedding for m in top_movies])
    
    combined = np.zeros(len(top_movies))
    candidates = 0
    for u in user_list:

        if not u.taste_positive:
            continue
        candidates += 1

        score = embeddings @ np.array(u.taste_positive)

        if u.taste_negative:
            score -= alpha * (embeddings @ np.array(u.taste_negative))
        combined += score
    combined /= candidates

    ranked_movies = np.argsort(-combined)[:limit_movies]

    return [top_movies[i] for i in ranked_movies]
        