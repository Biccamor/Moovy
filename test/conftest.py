"""
Współdzielone fixture'y dla testów unit.

Mockują bazę danych, autentykację i rate limiter —
testy nie wymagają Dockera, Postgresa ani modeli AI.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock
from uuid import uuid4

# ── Dodaj root projektu do sys.path ─────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── Pre-mock ciężkich zależności (GPU/ML) ────────────────────────────
# Mockujemy TYLKO moduły, których nie da się zaimportować.
# W Dockerze (gdzie torch/psycopg2 są zainstalowane) — zostawiamy prawdziwe.
# Lokalnie (bez tych paczek) — wstawiamy MagicMock.

_HEAVY_MODULES = [
    "FlagEmbedding",
    "flashrank",
    "torch",
    "sentence_transformers",
    "transformers",
    "pgvector",
    "pgvector.sqlalchemy",
    "psycopg2",
    "psycopg2.extensions",
    "psycopg2._psycopg",
    "langfuse",
]

for mod_name in _HEAVY_MODULES:
    if mod_name not in sys.modules:
        try:
            __import__(mod_name)
        except ImportError:
            sys.modules[mod_name] = MagicMock()

# ── Teraz bezpiecznie importujemy projekt ────────────────────────────

import scripts.dependencies as deps

# Nadpisz funkcje ładujące, żeby nic nie robiły
deps.load_model = MagicMock()
deps.load_db = MagicMock()
deps.load_reranker = MagicMock()

# Nadpisz engine żeby nie łączył się z bazą
deps.engine = MagicMock()

# Nadpisz create_tables
import database.main_db as main_db_mod
main_db_mod.create_tables = MagicMock()

from main import app
from database.main_db import get_session
from scripts.security import get_current_user, signJWT


# ── TestClient ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """TestClient z wyłączonym rate limiterem."""
    from fastapi.testclient import TestClient

    # Wyłączamy rate limiter — slowapi rzuca 429 na TestClient
    original_limit = deps.limiter.limit

    def _noop_limit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    deps.limiter.limit = _noop_limit

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    deps.limiter.limit = original_limit


# ── Mock bazy danych ────────────────────────────────────────────────

@pytest.fixture()
def mock_db():
    """
    Mockowana sesja SQLModel.
    Automatycznie override'uje dependency `get_session`.
    Czyści override po teście.
    """
    session = MagicMock()

    app.dependency_overrides[get_session] = lambda: session

    yield session

    app.dependency_overrides.pop(get_session, None)


# ── Helpery auth ────────────────────────────────────────────────────

@pytest.fixture()
def test_user_id():
    """Zwraca stały UUID do testów."""
    return str(uuid4())


@pytest.fixture()
def auth_headers(test_user_id):
    """
    Generuje prawdziwy JWT access token i zwraca dict z nagłówkiem Authorization.
    Użycie: client.post(..., headers=auth_headers)
    """
    tokens = signJWT(test_user_id)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.fixture()
def override_current_user(test_user_id):
    """
    Override'uje dependency get_current_user żeby zwracała
    stałego usera bez sprawdzania tokena.
    """
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": test_user_id,
        "type": "access",
    }

    yield test_user_id

    app.dependency_overrides.pop(get_current_user, None)
