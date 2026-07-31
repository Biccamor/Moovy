import pytest
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

def test_hybrid_search_no_anime_no_animation():
    import asyncio
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        pytest.skip("No DATABASE_URL set")

    engine = create_engine(db_url)
    dummy_query_vector = [0.0] * 768

    async def _run():
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

    asyncio.run(_run())
