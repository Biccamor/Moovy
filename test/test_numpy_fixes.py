"""
Testy sprawdzajace naprawione bledy numpy:
  "The truth value of an array with more than one element is ambiguous"

Pokrycie:
- _to_numpy()             : list, np.array
- _incremental_update()   : old_taste=None, lista, np.array
- _reverse_update()       : old_taste=None, np.array, count edge-cases
- fusion_ranker()         : taste jako np.array zamiast listy (glowna przyczyna bledu)
"""

import sys
import os
import numpy as np
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routers.rating_router import _to_numpy, _incremental_update, _reverse_update
from engine.taste_reranker import fusion_ranker


DIM = 8

def _rand(seed: int = 0):
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(DIM)
    return (v / np.linalg.norm(v)).tolist()

def _movie(embedding, title="Movie"):
    m = MagicMock()
    m.embedding = embedding
    m.title = title
    return {"movie": m, "score": 0.5}

def _user(taste_positive=None, taste_negative=None):
    u = MagicMock()
    u.taste_positive = taste_positive
    u.taste_negative = taste_negative
    return u


class TestToNumpy:
    def test_from_list(self):
        v = [1.0, 2.0, 3.0]
        result = _to_numpy(v)
        assert isinstance(result, np.ndarray)
        np.testing.assert_array_almost_equal(result, v)

    def test_from_numpy_float32(self):
        v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        result = _to_numpy(v)
        assert isinstance(result, np.ndarray)
        assert result.dtype == np.float64

    def test_no_ambiguous_truth_value(self):
        """np.array nie powinno rzucac ambiguous truth value przez _to_numpy."""
        v = np.ones(DIM)
        result = _to_numpy(v)
        assert result.shape == (DIM,)


class TestIncrementalUpdate:

    def test_old_taste_none(self):
        emb = _rand(1)
        result = _incremental_update(None, 0, emb, 1.0)
        assert isinstance(result, list) and len(result) == DIM

    def test_old_taste_as_list(self):
        result = _incremental_update(_rand(0), 3, _rand(1), 0.5)
        assert isinstance(result, list) and len(result) == DIM

    def test_old_taste_as_numpy_no_crash(self):
        """Kluczowy test: old_taste = np.array, dawniej crash."""
        old = np.array(_rand(0))
        result = _incremental_update(old, 3, _rand(1), 0.5)
        assert isinstance(result, list) and len(result) == DIM

    def test_embedding_as_numpy_no_crash(self):
        result = _incremental_update(_rand(0), 2, np.array(_rand(1)), 1.0)
        assert isinstance(result, list)

    def test_result_normalized(self):
        result = _incremental_update(_rand(0), 5, _rand(1), 1.0)
        assert abs(np.linalg.norm(result) - 1.0) < 1e-6

    def test_empty_old_taste_no_crash(self):
        result = _incremental_update([], 0, _rand(2), 1.0)
        assert isinstance(result, list)


class TestReverseUpdate:

    def test_none_taste_returns_none(self):
        result, count = _reverse_update(None, 5, _rand(0), 1.0)
        assert result is None and count == 0

    def test_zero_count_returns_none(self):
        result, count = _reverse_update(_rand(0), 0, _rand(1), 1.0)
        assert result is None and count == 0

    def test_count_one_returns_none(self):
        result, count = _reverse_update(_rand(0), 1, _rand(1), 1.0)
        assert result is None and count == 0

    def test_numpy_old_taste_no_crash(self):
        """Kluczowy test: old_taste = np.array, dawniej crash."""
        result, count = _reverse_update(np.array(_rand(0)), 3, _rand(1), 0.5)
        assert count == 2

    def test_decrements_count(self):
        _, count = _reverse_update(_rand(0), 5, _rand(1), 1.0)
        assert count == 4


class TestFusionRankerNumpyInputs:

    def test_taste_positive_as_numpy_no_crash(self):
        """Kluczowy test: taste_positive = np.array, dawniej crash."""
        movies = [_movie(_rand(i), str(i)) for i in range(5)]
        result = fusion_ranker([_user(taste_positive=np.array(_rand(0)))], movies, limit_movies=5)
        assert len(result) == 5

    def test_taste_negative_as_numpy_no_crash(self):
        movies = [_movie(_rand(i), str(i)) for i in range(5)]
        result = fusion_ranker(
            [_user(taste_positive=np.array(_rand(0)), taste_negative=np.array(_rand(1)))],
            movies, limit_movies=5,
        )
        assert len(result) == 5

    def test_empty_taste_positive_skips_user(self):
        movies = [_movie(_rand(i), str(i)) for i in range(3)]
        result = fusion_ranker([_user(taste_positive=[])], movies)
        assert result == movies

    def test_none_taste_positive_skips_user(self):
        movies = [_movie(_rand(i), str(i)) for i in range(3)]
        result = fusion_ranker([_user(taste_positive=None)], movies)
        assert result == movies

    def test_mixed_none_and_numpy(self):
        movies = [_movie(_rand(i), str(i)) for i in range(4)]
        result = fusion_ranker(
            [_user(taste_positive=np.array(_rand(0))), _user(taste_positive=None)],
            movies, limit_movies=4,
        )
        assert len(result) == 4
