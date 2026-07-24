"""
Testy jednostkowe sesji filmowej (lobby flow).

Pokrycie:
- Tworzenie sesji (sukces + brak auth)
- Dołączanie kodem (sukces, zły kod, duplikat, nie-LOBBY)
- Ustawianie preferencji (sukces, all_ready, nie-członek)
- Pobieranie stanu sesji (członek vs nie-członek)
- Usuwanie sesji (host vs nie-host)
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from uuid import uuid4, UUID

from database.database_setup import MovieSessionDB, User


# ─── Helpers ────────────────────────────────────────────────────────

def _make_mock_db_user(user_id: str, email: str = "host@test.pl"):
    """Tworzy mock obiektu User z bazy."""
    user = MagicMock(spec=User)
    user.user_id = UUID(user_id)
    user.email = email
    return user


def _make_mock_movie_session(
    session_id=None,
    host_id=None,
    invite_code="ABC123",
    meeting_type="EKIPA",
    status="LOBBY",
    members=None,
):
    """Tworzy mock obiektu MovieSessionDB."""
    ms = MagicMock(spec=MovieSessionDB)
    ms.session_id = session_id or uuid4()
    ms.host_id = UUID(host_id) if host_id else uuid4()
    ms.invite_code = invite_code
    ms.meeting_type = meeting_type
    ms.status = status
    ms.members = members or []
    ms.recommendations = None
    ms.room_session_id = None
    ms.created_at = "2026-05-09"
    return ms


# ═══════════════════════════════════════════════════════════════════
#  CREATE SESSION
# ═══════════════════════════════════════════════════════════════════

@patch("routers.session_router._generate_invite_code", return_value="XY1234")
@patch("routers.session_router.select")
def test_create_session_success(mock_select, mock_invite, client, mock_db, override_current_user):
    """Host tworzy sesję → 200, zwraca session_id i invite_code."""
    user_id = override_current_user
    mock_user = _make_mock_db_user(user_id)

    # session.exec(select(User)...).first() → mock_user
    mock_db.exec.return_value.first.return_value = mock_user

    response = client.post("/session/create", json={
        "meeting_type": "EKIPA",
    })

    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert data["invite_code"] == "XY1234"
    assert data["meeting_type"] == "EKIPA"

    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


def test_create_session_unauthenticated(client, mock_db):
    """Brak tokena → 401 (HTTPBearer zwraca 401 w FastAPI >= 0.109)."""
    response = client.post("/session/create", json={
        "meeting_type": "EKIPA",
    })

    assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════
#  JOIN SESSION
# ═══════════════════════════════════════════════════════════════════

@patch("routers.session_router.flag_modified")
@patch("routers.session_router.select")
def test_join_session_success(mock_select, mock_flag_modified, client, mock_db, override_current_user):
    """Guest dołącza poprawnym kodem → 200."""
    user_id = override_current_user
    host_id = str(uuid4())

    mock_session = _make_mock_movie_session(
        host_id=host_id,
        invite_code="JOINME",
        members=[{
            "user_id": host_id,
            "user_name": "host",
            "status": "pending",
            "preferences": None,
        }],
    )
    mock_user = _make_mock_db_user(user_id, email="guest@test.pl")

    # Pierwszy exec → MovieSessionDB (po invite_code)
    # Drugi exec → User (po user_id)
    mock_db.exec.return_value.first.side_effect = [mock_session, mock_user]
    mock_db.refresh = MagicMock()  # session.refresh() na mocku → no-op

    response = client.post("/session/join", json={
        "invite_code": "JOINME",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Dołączono do sesji"
    assert "session_id" in data


@patch("routers.session_router.select")
def test_join_session_invalid_code(mock_select, client, mock_db, override_current_user):
    """Zły kod zaproszenia → 404."""
    mock_db.exec.return_value.first.return_value = None

    response = client.post("/session/join", json={
        "invite_code": "BADCODE",
    })

    assert response.status_code == 404
    assert "Nieprawidłowy kod" in response.json()["detail"]


@patch("routers.session_router.select")
def test_join_session_already_member(mock_select, client, mock_db, override_current_user):
    """User już jest w sesji → 409 CONFLICT."""
    user_id = override_current_user

    mock_session = _make_mock_movie_session(
        invite_code="DUPL01",
        members=[{
            "user_id": user_id,
            "user_name": "existing",
            "status": "pending",
            "preferences": None,
        }],
    )

    mock_db.exec.return_value.first.return_value = mock_session

    response = client.post("/session/join", json={
        "invite_code": "DUPL01",
    })

    assert response.status_code == 409
    assert "Już jesteś członkiem" in response.json()["detail"]


@patch("routers.session_router.select")
def test_join_session_not_in_lobby(mock_select, client, mock_db, override_current_user):
    """Sesja nie w stanie LOBBY → 400."""
    mock_session = _make_mock_movie_session(
        invite_code="CLOSED",
        status="COMPLETED",
        members=[],
    )

    mock_db.exec.return_value.first.return_value = mock_session

    response = client.post("/session/join", json={
        "invite_code": "CLOSED",
    })

    assert response.status_code == 400
    assert "nie jest w stanie LOBBY" in response.json()["detail"]


# ═══════════════════════════════════════════════════════════════════
#  SET PREFERENCES
# ═══════════════════════════════════════════════════════════════════

@patch("routers.session_router.flag_modified")
def test_set_preferences_success(mock_flag_modified, client, mock_db, override_current_user):
    """Członek podaje preferencje → status zmienia się na ready."""
    user_id = override_current_user
    session_id = uuid4()

    mock_session = _make_mock_movie_session(
        session_id=session_id,
        members=[
            {"user_id": user_id, "user_name": "me", "status": "pending", "preferences": None},
            {"user_id": str(uuid4()), "user_name": "other", "status": "pending", "preferences": None},
        ],
    )

    mock_db.get.return_value = mock_session
    mock_db.refresh = MagicMock()  # session.refresh() na mocku → no-op

    response = client.put(f"/session/{session_id}/preferences", json={
        "preferences": {
            "vibes": ["LAUGH_RIOT"],
            "hard_nos": [],
            "max_runtime": 120,
            "allow_seen": False,
            "eras": [],
        }
    })

    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Preferencje zapisane, status: ready"
    assert data["all_ready"] is False  # drugi członek dalej pending


@patch("routers.session_router.flag_modified")
def test_set_preferences_all_ready(mock_flag_modified, client, mock_db, override_current_user):
    """Ostatni członek daje preferencje → all_ready=true, status=ALL_READY."""
    user_id = override_current_user
    session_id = uuid4()

    mock_session = _make_mock_movie_session(
        session_id=session_id,
        members=[
            {"user_id": user_id, "user_name": "me", "status": "pending", "preferences": None},
            {"user_id": str(uuid4()), "user_name": "already_ready", "status": "ready",
             "preferences": {"vibes": ["ADRENALINE"], "hard_nos": [], "max_runtime": 90, "allow_seen": False, "eras": []}},
        ],
    )

    mock_db.get.return_value = mock_session
    mock_db.refresh = MagicMock()  # session.refresh() na mocku → no-op

    response = client.put(f"/session/{session_id}/preferences", json={
        "preferences": {
            "vibes": ["DATE_NIGHT"],
            "hard_nos": ["SPINE_CHILLING"],
            "max_runtime": 150,
            "allow_seen": True,
            "eras": ["2020s"],
        }
    })

    assert response.status_code == 200
    data = response.json()
    assert data["all_ready"] is True
    assert data["session_status"] == "ALL_READY"


def test_set_preferences_not_member(client, mock_db, override_current_user):
    """Nie-członek próbuje ustawić preferencje → 403."""
    session_id = uuid4()

    # Sesja istnieje ale nie ma naszego user_id w members
    mock_session = _make_mock_movie_session(
        session_id=session_id,
        members=[
            {"user_id": str(uuid4()), "user_name": "stranger", "status": "pending", "preferences": None},
        ],
    )

    mock_db.get.return_value = mock_session

    response = client.put(f"/session/{session_id}/preferences", json={
        "preferences": {
            "vibes": ["LAUGH_RIOT"],
            "hard_nos": [],
            "max_runtime": 120,
            "allow_seen": False,
            "eras": [],
        }
    })

    assert response.status_code == 403
    assert "Nie jesteś członkiem" in response.json()["detail"]


# ═══════════════════════════════════════════════════════════════════
#  GET SESSION DETAILS
# ═══════════════════════════════════════════════════════════════════

def test_get_session_details_as_member(client, mock_db, override_current_user):
    """Członek sesji pobiera jej stan → 200 z pełnymi danymi."""
    user_id = override_current_user
    session_id = uuid4()

    mock_session = _make_mock_movie_session(
        session_id=session_id,
        host_id=user_id,
        members=[
            {"user_id": user_id, "user_name": "host", "status": "ready",
             "preferences": {"vibes": ["LAUGH_RIOT"], "hard_nos": [], "max_runtime": 120, "allow_seen": False, "eras": []}},
        ],
    )

    mock_db.get.return_value = mock_session

    response = client.get(f"/session/{session_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == str(session_id)
    assert data["status"] == "LOBBY"
    assert len(data["members"]) == 1
    assert data["members"][0]["user_name"] == "host"


def test_get_session_details_unauthorized(client, mock_db, override_current_user):
    """Nie-członek próbuje pobrać sesję → 403."""
    session_id = uuid4()

    mock_session = _make_mock_movie_session(
        session_id=session_id,
        host_id=str(uuid4()),  # inny host
        members=[
            {"user_id": str(uuid4()), "user_name": "somebody", "status": "pending", "preferences": None},
        ],
    )

    mock_db.get.return_value = mock_session

    response = client.get(f"/session/{session_id}")

    assert response.status_code == 403
    assert "Nie masz dostępu" in response.json()["detail"]


# ═══════════════════════════════════════════════════════════════════
#  DELETE SESSION
# ═══════════════════════════════════════════════════════════════════

def test_delete_session_by_host(client, mock_db, override_current_user):
    """Host zamyka sesję → 200."""
    user_id = override_current_user
    session_id = uuid4()

    mock_session = _make_mock_movie_session(
        session_id=session_id,
        host_id=user_id,
    )

    mock_db.get.return_value = mock_session

    response = client.delete(f"/session/{session_id}")

    assert response.status_code == 200
    assert response.json()["message"] == "Sesja została zamknięta"
    mock_db.delete.assert_called_once_with(mock_session)
    mock_db.commit.assert_called_once()


def test_delete_session_not_host(client, mock_db, override_current_user):
    """Nie-host próbuje zamknąć sesję → 403."""
    session_id = uuid4()

    mock_session = _make_mock_movie_session(
        session_id=session_id,
        host_id=str(uuid4()),  # inny host
    )

    mock_db.get.return_value = mock_session

    response = client.delete(f"/session/{session_id}")

    assert response.status_code == 403
    assert "Tylko host" in response.json()["detail"]
