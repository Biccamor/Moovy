"""
Testy jednostkowe fusion_ranker z engine/taste_reranker.py

Pokrycie:
- Brak żadnego taste → zwraca top_movies bez zmian
- Jeden user z taste_positive → filmy posortowane po similarity
- Jeden user z taste_positive + taste_negative → alpha odejmuje negative
- Wielu userów → wynik jest średnią
- limit_movies → obcina wynik
"""

import numpy as np
from unittest.mock import MagicMock

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.taste_reranker import fusion_ranker


# ─── Helpers ─────────────────────────────────────────────────────────

def _movie(embedding: list[float], title: str = "Movie") -> dict:
    """Tworzy mock wpisu top_movies w formacie hybrid_search."""
    m = MagicMock()
    m.embedding = embedding
    m.title = title
    return {"movie": m, "score": 0.5}


def _user(taste_positive=None, taste_negative=None) -> MagicMock:
    """Tworzy mock User z wektorami taste."""
    u = MagicMock()
    u.taste_positive = taste_positive
    u.taste_negative = taste_negative
    return u


def _axis(i: int, dim: int = 4) -> list[float]:
    """Wektor jednostkowy wzdłuż osi i — znormalizowany."""
    v = np.zeros(dim)
    v[i] = 1.0
    return v.tolist()


def _unit(dim: int = 4) -> list[float]:
    """Znormalizowany wektor jedynkowy."""
    v = np.ones(dim) / np.sqrt(dim)
    return v.tolist()


# ═══════════════════════════════════════════════════════════════════
#  Brak taste — early return
# ═══════════════════════════════════════════════════════════════════

def test_no_users_returns_top_movies():
    """Pusta lista userów → zwraca top_movies bez zmian."""
    movies = [_movie(_unit()), _movie(_unit())]
    result = fusion_ranker([], movies)
    assert result == movies


def test_all_users_no_taste_returns_top_movies():
    """Wszyscy userzy bez taste_positive → zwraca top_movies bez zmian."""
    users = [_user(taste_positive=None), _user(taste_positive=None)]
    movies = [_movie(_unit()), _movie(_unit())]
    result = fusion_ranker(users, movies)
    assert result == movies


def test_empty_movies_returns_empty():
    """Brak filmów → zwraca pustą listę."""
    users = [_user(taste_positive=_unit())]
    result = fusion_ranker(users, [])
    assert result == []


# ═══════════════════════════════════════════════════════════════════
#  Jeden user, tylko positive
# ═══════════════════════════════════════════════════════════════════

def test_single_user_ranks_by_similarity():
    """
    User lubi filmy w kierunku osi 0.
    Film A = oś 0 → similarity 1.0 (najlepszy)
    Film B = oś 1 → similarity 0.0 (gorszy)
    Oczekujemy: [A, B]
    """
    taste = _axis(0)
    movie_a = _movie(_axis(0), title="A")
    movie_b = _movie(_axis(1), title="B")

    result = fusion_ranker([_user(taste_positive=taste)], [movie_b, movie_a], limit_movies=2)

    assert result[0]["movie"].title == "A"
    assert result[1]["movie"].title == "B"


def test_single_user_limit_movies():
    """limit_movies obcina wynik do zadanej liczby."""
    taste = _axis(0)
    movies = [_movie(_axis(i % 4), title=str(i)) for i in range(10)]

    result = fusion_ranker([_user(taste_positive=taste)], movies, limit_movies=3)

    assert len(result) == 3


# ═══════════════════════════════════════════════════════════════════
#  Taste negative — alpha odejmuje
# ═══════════════════════════════════════════════════════════════════

def test_negative_taste_penalizes_similar_movies():
    """
    User kocha oś 0 (positive) i nienawidzi osi 1 (negative).
    Film A = oś 0 → score = 1.0 - 0*alpha = 1.0
    Film B = oś 1 → score = 0.0 - 1*alpha = -0.3
    Film C = oś 2 → score = 0.0 - 0*alpha = 0.0
    Oczekujemy kolejność: A, C, B
    """
    taste_pos = _axis(0)
    taste_neg = _axis(1)

    movie_a = _movie(_axis(0), title="A")
    movie_b = _movie(_axis(1), title="B")
    movie_c = _movie(_axis(2), title="C")

    result = fusion_ranker(
        [_user(taste_positive=taste_pos, taste_negative=taste_neg)],
        [movie_a, movie_b, movie_c],
        alpha=0.3,
        limit_movies=3,
    )

    titles = [r["movie"].title for r in result]
    assert titles[0] == "A"
    assert titles[-1] == "B"


def test_no_negative_taste_ignores_alpha():
    """User bez taste_negative → alpha nie ma wpływu na ranking."""
    taste_pos = _axis(0)
    movie_a = _movie(_axis(0), title="A")
    movie_b = _movie(_axis(1), title="B")

    result = fusion_ranker(
        [_user(taste_positive=taste_pos, taste_negative=None)],
        [movie_b, movie_a],
        limit_movies=2,
    )

    assert result[0]["movie"].title == "A"


# ═══════════════════════════════════════════════════════════════════
#  Wielu userów — averaged score
# ═══════════════════════════════════════════════════════════════════

def test_multiple_users_averaged():
    """
    User A kocha oś 0, User B kocha oś 1.
    Oba filmy w wyniku (remis ~0.5 każdy).
    """
    movie_x = _movie(_axis(0), title="X")
    movie_y = _movie(_axis(1), title="Y")

    result = fusion_ranker(
        [_user(taste_positive=_axis(0)), _user(taste_positive=_axis(1))],
        [movie_x, movie_y],
        limit_movies=2,
    )

    titles = {r["movie"].title for r in result}
    assert titles == {"X", "Y"}


def test_multiple_users_one_without_taste():
    """
    User A ma taste, User B nie ma.
    Tylko User A wpływa na ranking → film A na #1.
    """
    movie_a = _movie(_axis(0), title="A")
    movie_b = _movie(_axis(1), title="B")

    result = fusion_ranker(
        [_user(taste_positive=_axis(0)), _user(taste_positive=None)],
        [movie_b, movie_a],
        limit_movies=2,
    )

    assert result[0]["movie"].title == "A"


def test_dominant_user_wins():
    """Obaj userzy kochają oś 0 → film na osi 0 zdecydowanie wygrywa."""
    movie_a = _movie(_axis(0), title="A")
    movie_b = _movie(_axis(1), title="B")

    result = fusion_ranker(
        [_user(taste_positive=_axis(0)), _user(taste_positive=_axis(0))],
        [movie_b, movie_a],
        limit_movies=2,
    )

    assert result[0]["movie"].title == "A"


# ═══════════════════════════════════════════════════════════════════
#  Integralność danych
# ═══════════════════════════════════════════════════════════════════

def test_returns_movie_dicts_not_indices():
    """Wynik to lista dictów {"movie": ..., "score": ...}, nie indeksów."""
    movies = [_movie(_axis(0), title="A"), _movie(_axis(1), title="B")]

    result = fusion_ranker([_user(taste_positive=_axis(0))], movies, limit_movies=2)

    assert all(isinstance(r, dict) for r in result)
    assert all("movie" in r for r in result)


def test_original_list_not_mutated():
    """fusion_ranker nie modyfikuje oryginalnej listy top_movies."""
    movies = [_movie(_axis(0), title="A"), _movie(_axis(1), title="B")]
    original_order = [m["movie"].title for m in movies]

    fusion_ranker([_user(taste_positive=_axis(0))], movies, limit_movies=2)

    assert [m["movie"].title for m in movies] == original_order
