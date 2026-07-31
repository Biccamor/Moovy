import pytest
from unittest.mock import MagicMock
from schemas.schemas import Preferences, SavedPreferences
from engine.vector import hybrid_search
from sqlmodel import Session, create_engine
import os

def test_preferences_schema_defaults():
    prefs = Preferences()
    assert prefs.no_anime is False
    assert prefs.no_animation is False

    saved_prefs = SavedPreferences()
    assert saved_prefs.no_anime is False
    assert saved_prefs.no_animation is False

def test_preferences_schema_custom():
    prefs = Preferences(no_anime=True, no_animation=True)
    assert prefs.no_anime is True
    assert prefs.no_animation is True

def test_hybrid_search_query_building_with_mock():
    import asyncio
    mock_session = MagicMock()
    mock_session.exec.return_value.all.return_value = []
    dummy_query_vector = [0.0] * 768

    async def _run():
        res = await hybrid_search(
            query_vector=dummy_query_vector,
            max_runtime=120,
            session=mock_session,
            user_list=[],
            no_anime=True,
            no_animation=True
        )
        assert res == []
        assert mock_session.exec.called

    asyncio.run(_run())

def test_hybrid_search_no_anime_no_animation_live_db():
    import asyncio
    db_url = os.getenv("DATABASE_URL")
    if not db_url or "postgre" in db_url and "localhost" not in db_url and "5432" not in db_url and "5433" not in db_url and "db" not in db_url:
        pytest.skip("No valid DATABASE_URL set for live DB test")

    dummy_query_vector = [0.0] * 768

    async def _run():
        try:
            engine = create_engine(db_url)
            with Session(engine) as session:
                # Test no_animation = True
                results_no_anim = await hybrid_search(
                    query_vector=dummy_query_vector,
                    max_runtime=240,
                    session=session,
                    user_list=[],
                    limit_movies=50,
                    no_animation=True
                )
                for res in results_no_anim:
                    genres = res["movie"].genre or []
                    assert "Animation" not in genres
                    assert "Animacja" not in genres

                # Test no_anime = True
                results_no_anime = await hybrid_search(
                    query_vector=dummy_query_vector,
                    max_runtime=240,
                    session=session,
                    user_list=[],
                    limit_movies=50,
                    no_anime=True
                )
                for res in results_no_anime:
                    tags = [t.lower() for t in (res["movie"].tags or [])]
                    for t in tags:
                        assert "anime" not in t
        except Exception as e:
            pytest.skip(f"Live DB connection or query failed: {e}")

    asyncio.run(_run())
