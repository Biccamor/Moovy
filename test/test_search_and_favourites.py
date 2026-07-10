"""
Testy jednostkowe endpointów:
- GET /movies/search  (search_router)
- POST /preferences/favourite  (preference_router — add_favourites)

Pokrycie:
- Search: sukces, brak wyników, walidacja parametrów, znaki specjalne ILIKE
- Favourites: sukces (taste_positive=None i istniejący), film nie istnieje,
              za dużo filmów, cudzy user, user nie istnieje
"""

import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4
from scripts.dependencies import limiter
from datetime import date


@pytest.fixture(autouse=True)
def _disable_rate_limiter():
    """Wyłącza rate limiter na czas testów — unika 429."""
    limiter.enabled = False
    yield
    limiter.enabled = True


# ─── Helpers ────────────────────────────────────────────────────────

def _make_mock_movie(tmdb_id: int = 550, title: str = "Fight Club",
                     rating: float = 8.4, year: int = 1999,
                     embedding: list[float] | None = None):
    """Tworzy mock obiektu Movie."""
    movie = MagicMock()
    movie.movie_id = uuid4()
    movie.tmdb_id = tmdb_id
    movie.title = title
    movie.poster_path = f"/posters/{tmdb_id}.jpg"
    movie.release_date = date(year, 1, 1)
    movie.rating = rating
    movie.embedding = embedding or [0.1] * 768
    return movie


def _make_mock_user(user_id: str, taste_positive: list[float] | None = None):
    """Tworzy mock obiektu User z opcjonalnym taste_positive."""
    user = MagicMock()
    user.user_id = user_id
    user.taste_positive = taste_positive
    return user


# ═══════════════════════════════════════════════════════════════════
#  SEARCH — GET /movies/search
# ═══════════════════════════════════════════════════════════════════


class TestSearchMovies:
    """Testy endpointu wyszukiwania filmów."""

    # ─── Sukces — znaleziono filmy ─────────────────────────────────

    def test_search_returns_movies(self, client, mock_db, override_current_user):
        """Wyszukanie istniejącego tytułu → 200, lista wyników."""
        movies = [
            _make_mock_movie(550, "Fight Club", 8.4, 1999),
            _make_mock_movie(551, "Fight Night", 6.2, 2005),
        ]
        mock_db.exec.return_value.all.return_value = movies

        response = client.get("/movies/search", params={"title": "Fight"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["title"] == "Fight Club"
        assert data[1]["title"] == "Fight Night"

    # ─── Struktura odpowiedzi ──────────────────────────────────────

    def test_search_response_structure(self, client, mock_db, override_current_user):
        """Każdy wynik zawiera wymagane klucze."""
        movies = [_make_mock_movie()]
        mock_db.exec.return_value.all.return_value = movies

        response = client.get("/movies/search", params={"title": "Fight"})

        data = response.json()
        assert len(data) == 1
        expected_keys = {"movie_id", "title", "poster_path", "year"}
        assert expected_keys == set(data[0].keys())

    # ─── Brak wyników ──────────────────────────────────────────────

    def test_search_no_results(self, client, mock_db, override_current_user):
        """Brak pasujących filmów → 200, pusta lista."""
        mock_db.exec.return_value.all.return_value = []

        response = client.get("/movies/search", params={"title": "xyznonexistent"})

        assert response.status_code == 200
        assert response.json() == []

    # ─── Walidacja: brak parametru title ───────────────────────────

    def test_search_missing_title(self, client, mock_db, override_current_user):
        """Brak parametru title → 422 (validation error)."""
        response = client.get("/movies/search")

        assert response.status_code == 422

    # ─── Walidacja: pusty title ────────────────────────────────────

    def test_search_empty_title(self, client, mock_db, override_current_user):
        """Pusty string jako title → 422 (min_length=1)."""
        response = client.get("/movies/search", params={"title": ""})

        assert response.status_code == 422

    # ─── Walidacja: za długi title ─────────────────────────────────

    def test_search_title_too_long(self, client, mock_db, override_current_user):
        """Title dłuższy niż 200 znaków → 422."""
        response = client.get("/movies/search", params={"title": "A" * 201})

        assert response.status_code == 422

    # ─── Walidacja: limit poza zakresem ────────────────────────────

    def test_search_limit_too_high(self, client, mock_db, override_current_user):
        """limit > 50 → 422."""
        response = client.get("/movies/search", params={"title": "Fight", "limit": 100})

        assert response.status_code == 422

    def test_search_limit_zero(self, client, mock_db, override_current_user):
        """limit = 0 → 422 (ge=1)."""
        response = client.get("/movies/search", params={"title": "Fight", "limit": 0})

        assert response.status_code == 422

    # ─── Znaki specjalne ILIKE nie manipulują zapytaniem ───────────

    def test_search_special_chars_escaped(self, client, mock_db, override_current_user):
        """Znaki %, _ w tytule nie psują ILIKE — endpoint nie crashuje."""
        mock_db.exec.return_value.all.return_value = []

        response = client.get("/movies/search", params={"title": "100%_done"})

        assert response.status_code == 200

    # ─── Brak autoryzacji ──────────────────────────────────────────

    def test_search_no_auth(self, client, mock_db):
        """Brak tokena → 401 (HTTPBearer)."""
        response = client.get("/movies/search", params={"title": "Fight"})

        assert response.status_code == 401

    # ─── Customowy limit ───────────────────────────────────────────

    def test_search_custom_limit(self, client, mock_db, override_current_user):
        """Parametr limit jest przekazywany do zapytania."""
        mock_db.exec.return_value.all.return_value = [_make_mock_movie()]

        response = client.get("/movies/search", params={"title": "Fight", "limit": 5})

        assert response.status_code == 200


# ═══════════════════════════════════════════════════════════════════
#  FAVOURITES — POST /preferences/favourite
# ═══════════════════════════════════════════════════════════════════


class TestAddFavourites:
    """Testy endpointu dodawania ulubionych filmów."""

    # ─── Sukces — taste_positive jest None (pierwszy raz) ──────────

    @patch("routers.preference_router.np")
    @patch("routers.preference_router.select")
    def test_add_favourites_first_time(self, mock_select, mock_np,
                                       client, mock_db, override_current_user):
        """Pierwszy film dodany gdy taste_positive=None → ustawia wektor."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id, taste_positive=None)
        mock_movie = _make_mock_movie(tmdb_id=550)

        # Pierwsze .first() → user, drugie .first() → movie
        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie]
        mock_np.linalg.norm.return_value = 1.0

        response = client.post(
            "/preferences/favourite",
            params={"user_id": user_id},
            json=[550],
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Favourites saved"
        assert data["user_id"] == user_id

    # ─── Sukces — taste_positive już istnieje (dodaje wektor) ──────

    @patch("routers.preference_router.np")
    @patch("routers.preference_router.select")
    def test_add_favourites_accumulates_vectors(self, mock_select, mock_np,
                                                 client, mock_db, override_current_user):
        """Dodanie filmu gdy taste_positive istnieje → np.add zostaje wywołany."""
        user_id = override_current_user
        existing_vector = [0.5] * 768
        mock_user = _make_mock_user(user_id, taste_positive=existing_vector)
        mock_movie = _make_mock_movie(tmdb_id=550)

        mock_db.exec.return_value.first.side_effect = [mock_user, mock_movie]
        mock_np.add.return_value.tolist.return_value = [0.6] * 768
        mock_np.linalg.norm.return_value = 1.0

        response = client.post(
            "/preferences/favourite",
            params={"user_id": user_id},
            json=[550],
        )

        assert response.status_code == 200
        mock_np.add.assert_called_once()

    # ─── Błąd: za dużo filmów (>5) ────────────────────────────────

    @patch("routers.preference_router.select")
    def test_add_favourites_too_many(self, mock_select,
                                      client, mock_db, override_current_user):
        """Więcej niż 5 filmów → 406."""
        user_id = override_current_user

        response = client.post(
            "/preferences/favourite",
            params={"user_id": user_id},
            json=[1, 2, 3, 4, 5, 6],
        )

        assert response.status_code == 406
        assert "more than 5" in response.json()["detail"]

    # ─── Błąd: cudzy user ──────────────────────────────────────────

    @patch("routers.preference_router.select")
    def test_add_favourites_wrong_user(self, mock_select,
                                        client, mock_db, override_current_user):
        """Próba modyfikacji cudzych ulubionych → 403."""
        other_user_id = str(uuid4())

        response = client.post(
            "/preferences/favourite",
            params={"user_id": other_user_id},
            json=[550],
        )

        assert response.status_code == 403
        assert "can't change other user" in response.json()["detail"]

    # ─── Błąd: user nie istnieje ───────────────────────────────────

    @patch("routers.preference_router.select")
    def test_add_favourites_user_not_found(self, mock_select,
                                            client, mock_db, override_current_user):
        """User nie istnieje w bazie → 404."""
        user_id = override_current_user
        mock_db.exec.return_value.first.return_value = None

        response = client.post(
            "/preferences/favourite",
            params={"user_id": user_id},
            json=[550],
        )

        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]

    # ─── Błąd: film nie istnieje ───────────────────────────────────

    @patch("routers.preference_router.select")
    def test_add_favourites_movie_not_found(self, mock_select,
                                             client, mock_db, override_current_user):
        """Film nie istnieje w bazie → 404."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)

        # Pierwszy .first() → user, drugi .first() → None (brak filmu)
        mock_db.exec.return_value.first.side_effect = [mock_user, None]

        response = client.post(
            "/preferences/favourite",
            params={"user_id": user_id},
            json=[999999],
        )

        assert response.status_code == 404
        assert "Movie not found" in response.json()["detail"]

    # ─── Błąd: pusta lista ─────────────────────────────────────────

    @patch("routers.preference_router.select")
    def test_add_favourites_empty_list(self, mock_select,
                                        client, mock_db, override_current_user):
        """Pusta lista filmów → 200, ale nic nie robi (edge case)."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id)
        mock_db.exec.return_value.first.return_value = mock_user

        response = client.post(
            "/preferences/favourite",
            params={"user_id": user_id},
            json=[],
        )

        assert response.status_code == 200

    # ─── Brak autoryzacji ──────────────────────────────────────────

    def test_add_favourites_no_auth(self, client, mock_db):
        """Brak tokena → 401 (HTTPBearer)."""
        response = client.post(
            "/preferences/favourite",
            params={"user_id": str(uuid4())},
            json=[550],
        )

        assert response.status_code == 401

    # ─── Sukces: dokładnie 5 filmów (granica) ──────────────────────

    @patch("routers.preference_router.np")
    @patch("routers.preference_router.select")
    def test_add_favourites_exactly_five(self, mock_select, mock_np,
                                          client, mock_db, override_current_user):
        """Dokładnie 5 filmów → 200 (granica limitu)."""
        user_id = override_current_user
        mock_user = _make_mock_user(user_id, taste_positive=None)
        mock_movie = _make_mock_movie()

        # user + 5x movie
        mock_db.exec.return_value.first.side_effect = [mock_user] + [mock_movie] * 5
        mock_np.add.return_value.tolist.return_value = [0.5] * 768
        mock_np.linalg.norm.return_value = 1.0

        response = client.post(
            "/preferences/favourite",
            params={"user_id": user_id},
            json=[1, 2, 3, 4, 5],
        )

        assert response.status_code == 200
