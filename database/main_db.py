from sqlmodel import SQLModel, Session, text
import scripts.dependencies as d 
from database.database_setup import Movie, User, Room_Session, Rating, MovieSessionDB
def create_tables():    
    with d.engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    SQLModel.metadata.create_all(d.engine)    # type: ignore
    with d.engine.connect() as conn:
        conn.execute(text(
            " CREATE INDEX IF NOT EXISTS hnsw_movie"
            " ON movie USING hnsw"
            " (embedding vector_cosine_ops)"
            " WITH (m = 16, ef_construction = 128);"
        ))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm;"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_movie_title_trgm ON movie USING GIN (title gin_trgm_ops);"))
        conn.commit()


def get_session():
    with Session(d.engine) as session:
        yield session

if __name__ == "__main__":
    d.load_db()
    create_tables()
