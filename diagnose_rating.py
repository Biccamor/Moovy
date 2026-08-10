"""
Skrypt diagnostyczny — odtwarza dokładnie ścieżkę _execute_rate
żeby znaleźć przyczynę 500 na produkcji.
Uruchom: python diagnose_rating.py
"""
import os
import sys
import traceback

# Musi być uruchomiony z root projektu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

# Użyj LOCAL database URL
DATABASE_URL = os.getenv("DATABASE_URL_LOCAL") or os.getenv("DATABASE_URL")
print(f"[INFO] Łączę z: {DATABASE_URL}")

from sqlmodel import create_engine, Session, select
from database.database_setup import User, Movie, User_Interaction
from uuid import UUID
import numpy as np

engine = create_engine(DATABASE_URL, echo=True)  # echo=True pokaże SQL

TEST_USER_ID = UUID("16235c4a-7095-46ff-8951-b97ac84591e3")
TEST_MOVIE_ID = UUID("46d5268a-25ea-4fb4-b7f8-dd80c7183cfe")

with Session(engine) as session:
    print("\n=== KROK 1: Szukam usera ===")
    try:
        user = session.exec(select(User).where(User.user_id == TEST_USER_ID)).first()
        print(f"User: {user.user_id if user else 'NOT FOUND'}")
        if user:
            print(f"  taste_positive type: {type(user.taste_positive)}")
            print(f"  taste_positive len: {len(user.taste_positive) if user.taste_positive else 'None'}")
            print(f"  positive_count: {user.positive_count}")
            print(f"  taste_negative type: {type(user.taste_negative)}")
            print(f"  negative_count: {user.negative_count}")
    except Exception as e:
        print(f"BŁĄD: {e}")
        traceback.print_exc()

    print("\n=== KROK 2: Szukam filmu ===")
    try:
        movie = session.exec(select(Movie).where(Movie.movie_id == TEST_MOVIE_ID)).first()
        print(f"Movie: {movie.title if movie else 'NOT FOUND'}")
        if movie:
            print(f"  embedding type: {type(movie.embedding)}")
            print(f"  embedding len: {len(movie.embedding) if movie.embedding else 'None'}")
            has_emb = bool(movie.embedding and len(movie.embedding) > 0)
            print(f"  has embedding: {has_emb}")
    except Exception as e:
        print(f"BŁĄD: {e}")
        traceback.print_exc()

    print("\n=== KROK 3: Szukam istniejącej interakcji ===")
    try:
        existing = session.exec(
            select(User_Interaction).where(
                User_Interaction.user_id == TEST_USER_ID,
                User_Interaction.movie_id == TEST_MOVIE_ID,
            )
        ).first()
        print(f"Existing: {existing.status if existing else 'None'}")
    except Exception as e:
        print(f"BŁĄD: {e}")
        traceback.print_exc()

    print("\n=== KROK 4: Tworzę User_Interaction ===")
    try:
        if existing:
            print(f"  Zmieniam status z {existing.status} na LIKE")
            existing.status = "LIKE"
        else:
            print("  Tworzę nowy User_Interaction")
            new_interaction = User_Interaction(
                user_id=TEST_USER_ID,
                movie_id=TEST_MOVIE_ID,
                status="LIKE"
            )
            print(f"  Utworzono: {new_interaction}")
            session.add(new_interaction)
    except Exception as e:
        print(f"BŁĄD: {e}")
        traceback.print_exc()

    print("\n=== KROK 5: session.add(user) ===")
    try:
        session.add(user)
        print("  OK")
    except Exception as e:
        print(f"BŁĄD: {e}")
        traceback.print_exc()

    print("\n=== KROK 6: session.commit() ===")
    try:
        session.commit()
        print("  COMMIT OK!")
    except Exception as e:
        print(f"BŁĄD COMMIT: {e}")
        traceback.print_exc()
        session.rollback()

    # Cleanup - usuń testową interakcję
    print("\n=== CLEANUP ===")
    try:
        cleanup = session.exec(
            select(User_Interaction).where(
                User_Interaction.user_id == TEST_USER_ID,
                User_Interaction.movie_id == TEST_MOVIE_ID,
            )
        ).first()
        if cleanup:
            session.delete(cleanup)
            session.commit()
            print("  Wyczyszczono testową interakcję")
    except Exception:
        session.rollback()

print("\n=== GOTOWE ===")
