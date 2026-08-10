"""
Migracja: dodaje brakujące kolumny do tabeli app_user na produkcji.
Uruchom raz: python scripts/migrate_add_nickname.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text, inspect

urls = [url for url in [os.getenv("DATABASE_URL"), os.getenv("DATABASE_URL_LOCAL")] if url]

engine = None
for url in urls:
    try:
        print(f"[MIGRATE] Trying connection to: {url}")
        test_engine = create_engine(url)
        with test_engine.connect() as conn:
            pass
        engine = test_engine
        print(f"[MIGRATE] Successfully connected to: {url}")
        break
    except Exception as e:
        print(f"[MIGRATE] Connection failed for {url}: {e}")

if not engine:
    raise RuntimeError("Could not connect to database with any available URL")

with engine.connect() as conn:
    inspector = inspect(engine)
    existing_columns = {col["name"] for col in inspector.get_columns("app_user")}
    print(f"[MIGRATE] Existing columns in app_user: {existing_columns}")

    migrations = []

    if "nickname" not in existing_columns:
        migrations.append("ALTER TABLE app_user ADD COLUMN nickname VARCHAR(30) DEFAULT NULL")
        print("[MIGRATE] Will add: nickname")
    
    if "profile_picture" not in existing_columns:
        migrations.append("ALTER TABLE app_user ADD COLUMN profile_picture TEXT DEFAULT NULL")
        print("[MIGRATE] Will add: profile_picture")

    if not migrations:
        print("[MIGRATE] Nothing to migrate — all columns exist.")
    else:
        for sql in migrations:
            print(f"[MIGRATE] Running: {sql}")
            conn.execute(text(sql))
        conn.commit()
        print("[MIGRATE] Done! All columns added.")

    # Verify
    updated_columns = {col["name"] for col in inspector.get_columns("app_user")}
    print(f"[MIGRATE] Final columns in app_user: {updated_columns}")
