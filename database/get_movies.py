import requests
from sqlmodel import Session, create_engine
from engine.vector import create_vector
from database.database_setup import Movie
import scripts.dependencies as d
import time
import concurrent.futures
from requests.exceptions import RequestException
from sqlalchemy.dialects.postgresql import insert
from datetime import date
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")
TMDB_API = os.getenv("TMDB_API")
engine = create_engine(DATABASE_URL, #type: ignore
                        echo=True,
                        pool_size=20,          
                        max_overflow=10,      
                        pool_timeout=60,      
                        pool_recycle=1800)
headers = {
    "accept": "application/json",
    "Authorization": f"Bearer {BEARER_TOKEN}"
}
d.load_model()  

PAGES = 400
MAX_RETRIES = 5

http = requests.Session()
http.headers.update(headers)

def fetch_details(movie_id: int) -> dict:
    url = f"https://api.themoviedb.org/3/movie/{movie_id}?append_to_response=keywords"
    
    for attempt in range(MAX_RETRIES):
        try:
            response = http.get(url, timeout=10)
            
            if response.status_code == 429:
                wait = 2 ** attempt  # 1, 2, 4, 8, 16 sekund
                print(f"Rate limit dla {movie_id}, czekam {wait}s")
                time.sleep(wait)
                continue
                
            if response.status_code == 200:
                return response.json()
                
            print(f"Status {response.status_code} dla {movie_id}")
            
        except Exception as e:
            wait = 2 ** attempt
            print(f"Błąd sieci dla {movie_id}: {e}, czekam {wait}s")
            time.sleep(wait)
    
    print(f"Pomijam film {movie_id} po {MAX_RETRIES} próbach")
    return {}  # pusty dict zamiast wiecznej rekurencji

def create_movie_prompt(genres: list, movie_title: str, desc: str, keywords: list):
    genres_str = ", ".join(genres)
    keywords_str = ", ".join(keywords)

    prompt = f"movie title is {movie_title}, the genres are {genres_str}, and the description overview is {desc}. the words that describe movie {keywords_str}"

    return prompt

def get_genres() -> dict[str, str]:
    """
    Function to generate dict of genres that tmbd have based on url 
    """
    url_genres = "https://api.themoviedb.org/3/genre/movie/list?language=en"
    response = requests.get(url_genres, headers=headers, timeout=30).json()["genres"]
    genres_dict = {}
    for genre in response:
        genres_dict.update({genre['id']:  genre['name']})
    return genres_dict

def save_batch(session: Session, movie_batch: list) -> None:
    try:
        for movie_obj in movie_batch:
            data = movie_obj.model_dump(exclude={"movie_id"})
            stmt = insert(Movie).values(data).on_conflict_do_nothing(index_elements=['tmdb_id'])
            session.exec(stmt)
        session.commit()
        print(f"Zapisano {len(movie_batch)} filmów")
    except Exception as e:
        session.rollback()
        print(f"Błąd zapisu: {e}")
def add_movies(start_page: int = 1):
    genre_dict = get_genres()

    with Session(engine) as session:
        movie_batch = []
        
        for page in range(start_page, PAGES + 1):
            print(f"Strona {page}/{PAGES}")
            
            try:
                url = f"https://api.themoviedb.org/3/movie/popular?language=en-US&page={page}"
                movies_list = http.get(url, timeout=10).json().get("results", [])
                movies_list = [m for m in movies_list if m.get("vote_count", 0) >= 100]
            except Exception as e:
                print(f"Błąd pobierania strony {page}: {e}, pomijam")
                continue

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                all_details = list(executor.map(
                    lambda m: fetch_details(m['id']), movies_list
                ))

            page_prompts = []
            page_movies_data = []

            for movie, details in zip(movies_list, all_details):
                if not details:  # pominięty film
                    continue

                vote_count = details.get("vote_count", movie.get("vote_count", 0))
                if vote_count is None or vote_count < 100:
                    continue
                    
                runtime = details.get("runtime", 0)
                keywords = [k["name"] for k in details.get("keywords", {}).get("keywords", [])]
                genres = [genre_dict.get(g_id, "") for g_id in movie['genre_ids']]
                
                page_prompts.append(create_movie_prompt(genres, movie['title'], movie['overview'], keywords))
                page_movies_data.append({
                    "movie": movie, "runtime": runtime, "keywords": keywords, "genres": genres
                })

            if not page_prompts:
                continue

            import asyncio
            embeddings = asyncio.run(create_vector(page_prompts))

            for data, embedding in zip(page_movies_data, embeddings):
                m = data["movie"]
                movie_batch.append(Movie(
                    tmdb_id=m['id'],
                    title=m['title'],
                    description=m['overview'],
                    genre=data["genres"],
                    release_date=date.fromisoformat(m['release_date']) if m.get('release_date') else None,
                    rating=m['vote_average'],
                    embedding=embedding,
                    runtime=data["runtime"],
                    tags=data["keywords"],
                    poster_path=m.get('poster_path')
                ))

            if page % 3 == 0 or page == PAGES:
                save_batch(session, movie_batch)
                movie_batch = []

add_movies(start_page=1)