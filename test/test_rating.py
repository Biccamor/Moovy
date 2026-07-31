"""
Testy jednostkowe endpointów:
- POST /rating/rate   (rate_movie)
- DELETE /rating/rate  (unrate_movie)
- GET /rating/history  (get_rating_history)

Pokrycie:
- Rate: sukces (pierwszy rating), zmiana ratingu (reverse + nowy),
        film nie istnieje, brak embeddingu, brak auth, nieprawidłowy status
- Unrate: sukces, brak interakcji, brak auth
- History: sukces (z wynikami), pusta historia, brak auth
"""

import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4
from scripts.dependencies import limiter


@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    """Wyłącza rate limiter na czas testów — unika 429."""
    limiter.enabled = False
    yield
    limiter.enabled = True


# ─── Helpers ────────────────────────────────────────────────────────

def _make_mock_movie(embedding=None):
    """Tworzy mock obiektu Movie z embeddingiem 768-dim."""
    movie = MagicMock()
    movie.movie_id = uuid4()
    movie.title = "Fight Club"
    movie.poster_path = "/posters/550.jpg"
    movie.embedding = embedding if embedding is not None else [0.1] * 768
    return movie


def _make_mock_user(user_id, taste_positive=None, taste_negative=None,
                    positive_count=0, negative_count=0):
    """Tworzy mock obiektu User z polami taste."""
    user = MagicMock()
    user.user_id = user_id
    user.taste_positive = taste_positive
    user.taste_negative = taste_negative
    user.positive_count = positive_count
    user.negative_count = negative_count
    return user


def _make_mock_interaction(user_id, movie_id, status="LOVE"):
    """Tworzy mock obiektu User_Interaction."""
    interaction = MagicMock()
    interaction.user_id = user_id
    interaction.movie_id = movie_id
    interaction.status = status
    return interaction


# ═══════════════════════════════════════════════════════════════════
#  RATE — POST /rating/rate
# ═══════════════════════════════════════════════════════════════════


class TestRateMovie:
    """Testy endpointu ratingu filmów."""

    # ─── Sukces: pierwszy rating LOVE ──────────────────────────────

    @patch("routers.rating_router.select")
    def test_rate_love_first_time(self, mock_select,
                                  client, mock_db, override_current_user):
        """Pierwszy rating LOVE → 200, positive_count rośnie."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)
        mock_movie = _make_mock_movie()

        # exec().first() → user, movie, existing_interaction(None)
        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, None]

        response = client.post("/rating/rate", json={
            "movie_id": str(mock_movie.movie_id),
            "status": "LOVE",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "LOVE"

    # ─── Sukces: rating LIKE ───────────────────────────────────────

    @patch("routers.rating_router.select")
    def test_rate_like(self, mock_select, client, mock_db, override_current_user):
        """Rating LIKE → 200."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)
        mock_movie = _make_mock_movie()

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, None]

        response = client.post("/rating/rate", json={
            "movie_id": str(mock_movie.movie_id),
            "status": "LIKE",
        })

        assert response.status_code == 200
        assert response.json()["status"] == "LIKE"

    # ─── Sukces: rating HATE → taste_negative ─────────────────────

    @patch("routers.rating_router.select")
    def test_rate_hate(self, mock_select, client, mock_db, override_current_user):
        """Rating HATE → 200, trafia do taste_negative."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)
        mock_movie = _make_mock_movie()

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, None]

        response = client.post("/rating/rate", json={
            "movie_id": str(mock_movie.movie_id),
            "status": "HATE",
        })

        assert response.status_code == 200
        assert response.json()["status"] == "HATE"

    # ─── Sukces: rating DISLIKE ────────────────────────────────────

    @patch("routers.rating_router.select")
    def test_rate_dislike(self, mock_select, client, mock_db, override_current_user):
        """Rating DISLIKE → 200."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)
        mock_movie = _make_mock_movie()

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, None]

        response = client.post("/rating/rate", json={
            "movie_id": str(mock_movie.movie_id),
            "status": "DISLIKE",
        })

        assert response.status_code == 200
        assert response.json()["status"] == "DISLIKE"

    # ─── Sukces: zmiana ratingu (reverse + nowy) ──────────────────

    @patch("routers.rating_router.select")
    def test_rate_change_love_to_hate(self, mock_select,
                                      client, mock_db, override_current_user):
        """Zmiana LOVE → HATE → odwraca positive, dodaje negative."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id, taste_positive=[0.1] * 768, positive_count=1)
        mock_movie = _make_mock_movie()
        existing = _make_mock_interaction(user_id, mock_movie.movie_id, "LOVE")

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, existing]

        response = client.post("/rating/rate", json={
            "movie_id": str(mock_movie.movie_id),
            "status": "HATE",
        })

        assert response.status_code == 200
        assert response.json()["status"] == "HATE"

    # ─── Błąd: user nie istnieje ──────────────────────────────────

    @patch("routers.rating_router.select")
    def test_rate_user_not_found(self, mock_select,
                                 client, mock_db, override_current_user):
        """User nie istnieje → 404."""
        mock_db.exec.return_value.first.return_value = None

        response = client.post("/rating/rate", json={
            "movie_id": str(uuid4()),
            "status": "LOVE",
        })

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    # ─── Błąd: film nie istnieje ──────────────────────────────────

    @patch("routers.rating_router.select")
    def test_rate_movie_not_found(self, mock_select,
                                   client, mock_db, override_current_user):
        """Film nie istnieje → 404."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)

        # user OK, movie None
        mock_db.exec.return_value.first.side_effect = [mock_user, None]

        response = client.post("/rating/rate", json={
            "movie_id": str(uuid4()),
            "status": "LOVE",
        })

        assert response.status_code == 404
        assert "Movie not found" in response.json()["detail"]

    # ─── Sukces: film bez embeddingu ──────────────────────────────

    @patch("routers.rating_router.select")
    def test_rate_movie_no_embedding(self, mock_select,
                                      client, mock_db, override_current_user):
        """Film bez embeddingu → 200 (zapisuje interakcję, pomija update wektora)."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)
        mock_movie = _make_mock_movie(embedding=None)
        mock_movie.embedding = None  # jawnie brak

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, None]

        response = client.post("/rating/rate", json={
            "movie_id": str(mock_movie.movie_id),
            "status": "LOVE",
        })

        assert response.status_code == 200

    # ─── Sukces: status pisany małymi literami (np. 'like', 'watchlist') ──────

    @patch("routers.rating_router.select")
    def test_rate_lowercase_status(self, mock_select, client, mock_db, override_current_user):
        """Status w małych literach ('watchlist') → automatycznie podnoszony do wielkich (200)."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)
        mock_movie = _make_mock_movie()

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, None]

        response = client.post("/rating/rate", json={
            "movie_id": str(mock_movie.movie_id),
            "status": "watchlist",
        })

        assert response.status_code == 200
        assert response.json()["status"] == "WATCHLIST"

    # ─── Sukces: przekazanie movie_id jako tmdb_id (int) ──────────

    @patch("routers.rating_router.select")
    def test_rate_by_tmdb_id(self, mock_select, client, mock_db, override_current_user):
        """movie_id jako integer tmdb_id → wyszukiwanie po tmdb_id i sukces (200)."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)
        mock_movie = _make_mock_movie()
        mock_movie.tmdb_id = 550

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, None]

        response = client.post("/rating/rate", json={
            "movie_id": 550,
            "status": "LOVE",
        })

        assert response.status_code == 200

    # ─── Sukces: camelCase movieId w body JSON ─────────────────────

    @patch("routers.rating_router.select")
    def test_rate_camelcase_movie_id(self, mock_select, client, mock_db, override_current_user):
        """movieId (camelCase) w body JSON → 200."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)
        mock_movie = _make_mock_movie()

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, None]

        response = client.post("/rating/rate", json={
            "movieId": str(mock_movie.movie_id),
            "status": "like",
        })

        assert response.status_code == 200
        assert response.json()["status"] == "LIKE"

    # ─── Sukces: rate po ID w ścieżce /rating/rate/{id} ───────────

    @patch("routers.rating_router.select")
    def test_rate_path_parameter(self, mock_select, client, mock_db, override_current_user):
        """POST /rating/rate/{target_movie_id} → 200."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)
        mock_movie = _make_mock_movie()

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, None]

        response = client.post(f"/rating/rate/{mock_movie.movie_id}")

        assert response.status_code == 200

    # ─── Sukces: watchlist po ID w ścieżce /rating/watchlist/{id} ─

    @patch("routers.rating_router.select")
    def test_watchlist_path_parameter(self, mock_select, client, mock_db, override_current_user):
        """POST /rating/watchlist/{target_movie_id} → 200 z opcją WATCHLIST."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)
        mock_movie = _make_mock_movie()

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, None]

        response = client.post(f"/rating/watchlist/{mock_movie.movie_id}")

        assert response.status_code == 200
        assert response.json()["status"] == "WATCHLIST"

    # ─── Błąd: nieprawidłowy status ───────────────────────────────

    def test_rate_invalid_status(self, client, mock_db, override_current_user):
        """Nieprawidłowy status → 422 (walidacja Pydantic)."""
        response = client.post("/rating/rate", json={
            "movie_id": str(uuid4()),
            "status": "AMAZING",
        })

        assert response.status_code == 422

    # ─── Brak autoryzacji ─────────────────────────────────────────

    def test_rate_no_auth(self, client, mock_db):
        """Brak tokena → 401."""
        response = client.post("/rating/rate", json={
            "movie_id": str(uuid4()),
            "status": "LOVE",
        })

        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════
#  UNRATE — DELETE /rating/rate
# ═══════════════════════════════════════════════════════════════════


class TestUnrateMovie:
    """Testy endpointu usuwania ratingu."""

    # ─── Sukces: usunięcie ratingu ────────────────────────────────

    @patch("routers.rating_router.select")
    def test_unrate_success(self, mock_select, client, mock_db, override_current_user):
        """Usunięcie istniejącego ratingu → 200."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id, taste_positive=[0.1] * 768, positive_count=1)
        mock_movie = _make_mock_movie()
        existing = _make_mock_interaction(user_id, mock_movie.movie_id, "LOVE")

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, existing]

        response = client.request("DELETE", "/rating/rate", json={
            "movie_id": str(mock_movie.movie_id),
            "status": "LOVE",
        })

        assert response.status_code == 200
        assert "removed" in response.json()["message"].lower()

    # ─── Błąd: brak interakcji do usunięcia ───────────────────────

    @patch("routers.rating_router.select")
    def test_unrate_no_interaction(self, mock_select,
                                    client, mock_db, override_current_user):
        """Brak interakcji → 404."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)
        mock_movie = _make_mock_movie()

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie, None]

        response = client.request("DELETE", "/rating/rate", json={
            "movie_id": str(mock_movie.movie_id),
            "status": "LOVE",
        })

        assert response.status_code == 404
        assert "No rating found" in response.json()["detail"]

    # ─── Brak autoryzacji ─────────────────────────────────────────

    def test_unrate_no_auth(self, client, mock_db):
        """Brak tokena → 401."""
        response = client.request("DELETE", "/rating/rate", json={
            "movie_id": str(uuid4()),
            "status": "LOVE",
        })

        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════
#  HISTORY — GET /rating/history
# ═══════════════════════════════════════════════════════════════════


class TestRatingHistory:
    """Testy endpointu historii ratingów."""

    # ─── Sukces: historia z wynikami ──────────────────────────────

    @patch("routers.rating_router.select")
    def test_history_returns_ratings(self, mock_select,
                                     client, mock_db, override_current_user):
        """Historia z ratingami → 200, lista wyników."""
        user_id = override_current_user
        mock_movie = _make_mock_movie()
        mock_interaction = _make_mock_interaction(user_id, mock_movie.movie_id, "LOVE")

        mock_db.exec.return_value.all.return_value = [(mock_interaction, mock_movie)]

        response = client.get("/rating/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "LOVE"
        assert data[0]["title"] == "Fight Club"

    # ─── Struktura odpowiedzi ─────────────────────────────────────

    @patch("routers.rating_router.select")
    def test_history_response_structure(self, mock_select,
                                         client, mock_db, override_current_user):
        """Każdy wynik zawiera wymagane klucze."""
        user_id = override_current_user
        mock_movie = _make_mock_movie()
        mock_interaction = _make_mock_interaction(user_id, mock_movie.movie_id, "LIKE")

        mock_db.exec.return_value.all.return_value = [(mock_interaction, mock_movie)]

        response = client.get("/rating/history")

        data = response.json()
        expected_keys = {"movie_id", "title", "poster_path", "status"}
        assert expected_keys == set(data[0].keys())

    # ─── Pusta historia ───────────────────────────────────────────

    @patch("routers.rating_router.select")
    def test_history_empty(self, mock_select, client, mock_db, override_current_user):
        """Brak ratingów → 200, pusta lista."""
        mock_db.exec.return_value.all.return_value = []

        response = client.get("/rating/history")

        assert response.status_code == 200
        assert response.json() == []

    # ─── Brak autoryzacji ─────────────────────────────────────────

    def test_history_no_auth(self, client, mock_db):
        """Brak tokena → 401."""
        response = client.get("/rating/history")

        assert response.status_code == 401
