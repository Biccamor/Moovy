# MovieNight — AI-Powered Group Movie Recommendation Engine

MovieNight is a backend API that solves a surprisingly hard problem: finding a movie that an entire group actually wants to watch. It aggregates individual preferences, mood signals, and constraints from multiple users into a single intelligent recommendation session powered by semantic search and the Groq inference API.

---

## Architecture Overview

```
User Preferences → Vibe Aggregation → Prompt Construction
       → BGE-Base-en-v1.5 Embedding (768d) → pgvector Hybrid Search
            → FlashRank Reranking → Taste Fusion Reranking (Multi-User Taste Vectors) → Groq LLM Decision → Response
```

The recommendation pipeline runs in seven stages:

1. **Preference Aggregation** — Collects each user's vibes and maps them via `VIBE_MAP` to genre frequencies and descriptive keywords. Runtime constraints and era filters are merged across the group.
2. **Prompt Construction** — Builds a structured natural-language prompt from the aggregated group profile.
3. **Vector Embedding** — Encodes the prompt into a 768-dimensional vector using `BAAI/bge-base-en-v1.5` loaded locally.
4. **Hybrid Search** — Queries PostgreSQL + pgvector using combined vector similarity and metadata filters.
5. **FlashRank Reranking** — Applies `FlashRank` (`ms-marco-MiniLM-L-12-v2`) to reorder candidates against the prompt.
6. **Taste Fusion Reranking** — Incorporates the long-term preferences of all session members. It scores candidate movies using their embeddings against each user's `taste_positive` and `taste_negative` vectors. Negative tastes are penalized (using `alpha = 0.3` scaling) to ensure no group member gets a movie they hate. The scores are averaged to yield the top candidates.
7. **LLM Decision** — Passes the top 15 candidates to **Groq API** (Llama 3 8B) for final selection with structured reasoning. Groq's inference speed eliminates the latency bottleneck of local model hosting.

---

## Tech Stack

| Layer            | Technology                               |
|------------------|------------------------------------------|
| Framework        | FastAPI (Python 3.11)                    |
| Database         | PostgreSQL 17 + pgvector                 |
| ORM              | SQLModel + SQLAlchemy                    |
| Embeddings       | SentenceTransformers (BGE-Base-v1.5)     |
| Reranking        | FlashRank (MiniLM-L-12-v2)               |
| LLM              | Groq API (Llama 3 8B)                    |
| Auth             | JWT (PyJWT) + Argon2 password hashing    |
| Containerization | Docker + Docker Compose                  |
| Observability    | Langfuse (LLM Tracing & Observability)   |

---

## Key Features

**Group-aware recommendation engine**
Users join a shared session via invite code. Each user submits their own vibe preferences, hard exclusions, and runtime constraints. The engine merges all inputs and reasons over them as a single group profile.

**Vibe system**
Instead of genre dropdowns, users express mood through semantic labels (`PIZZA_CHILL`, `DATE_NIGHT`, `MIND_BENDER`, etc.). Each vibe maps to weighted genre frequencies and descriptive keywords used to construct the embedding prompt.

**Hybrid semantic search**
Movie catalogue is pre-embedded at 768 dimensions. Queries combine pgvector cosine similarity with metadata filters (era, runtime, content exclusions) for precision retrieval.

**Taste Fusion Ranker (Multi-User Personalization)**
Integrates long-term profile data directly into the group flow. It scores search results using the dot product between the movie embeddings and each user's dynamic `taste_positive` and `taste_negative` vectors. It applies an `alpha` penalty for negative preferences to prevent recommending films anyone in the session strongly dislikes, averaging user scores for a democratic group recommendation.

**Observability & Tracing**
Integrated with **Langfuse** for tracing, prompt versioning, latency tracking, cost monitoring, and LLM output evaluation.

**Continuous Integration (GitHub Actions)**
Every push triggers an automated pipeline with three stages:
- **Linting** — enforces code style and formatting standards
- **Security scanning** — Bandit static analysis for common Python vulnerabilities
- **Regression testing** — Pytest suite with build caching for optimized execution times

**Cloud-ready deployment**
The application is containerized and structured for Continuous Deployment. Docker Compose handles local orchestration; the same container setup is the deployment target for cloud-native hosting.

**Security**
- Argon2 password hashing
- JWT access tokens with refresh token rotation
- Per-endpoint rate limiting (strict limits on heavy LLM routes)
- Max body payload size limit middleware (protects against DoS)

---

## Project Structure

```
movieNight/
├── main.py                        # App entry point, lifespan, middleware
├── compose.yaml                   # Docker Compose (API + PostgreSQL)
├── compose.prod.yaml              # Production Docker Compose
├── routers/
│   ├── auth_router.py             # Register, login, token refresh, delete account
│   ├── session_router.py          # Session creation, lobby management, preferences
│   ├── recommendation_router.py   # AI recommendations (orchestrated pipelines)
│   ├── profile_router.py          # User nicknames & base64 profile pictures
│   ├── rating_router.py           # Movie rating (LIKE, LOVE, HATE, DISLIKE) and vector updating
│   ├── movies_router.py           # Search movie titles
│   └── metadata_router.py         # Available vibes, eras, and statuses
├── engine/
│   ├── recommendation_service.py  # Full recommendation pipeline orchestration
│   ├── vector.py                  # Embedding creation & hybrid search
│   ├── llm_decider.py             # LLM-powered final selection
│   ├── taste_reranker.py          # Reranking based on user's profile taste vectors
│   └── prompts.py                 # Vibe mappings & prompt templates
├── database/
│   ├── main_db.py                 # Engine setup, session management, schema setup
│   ├── database_setup.py          # SQLModel table definitions (User, Movie, Session, Rating, etc.)
│   └── get_movies.py              # Movie data ingestion
├── schemas/
│   ├── schemas.py                 # Core Pydantic request/response models
│   └── llm_schemas.py             # Structured output schemas for LLM responses
└── test/                          # Comprehensive Pytest test suite (scenarios, fusion, rating, auth)
```

---

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Groq API key (free tier available at [console.groq.com](https://console.groq.com))

### Setup

```bash
# Clone the repository
git clone https://github.com/your-username/movieNight.git
cd movieNight

# Configure environment
cp .env.example .env
# Edit .env with your values (DATABASE_URL, GROQ_API_KEY, SECRET_KEY, LANGFUSE keys)

# Start all services
docker compose up --build
```

**Environment variables (`.env`):**
```env
DATABASE_URL=postgresql://user:password@db:5432/movienight
GROQ_API_KEY=your-groq-api-key
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE=25
# Langfuse config (Optional but recommended)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

The Compose file starts two services:
- PostgreSQL 17 with pgvector — port `5433`
- MovieNight API — port `8010` with hot reload

API docs available at `http://localhost:8010/docs`.

---

## API Reference

### 1. Authentication — `/auth`
* `POST /auth/register` — Create a new account
* `POST /auth/login` — Login and receive JWT access & refresh tokens
* `POST /auth/refresh` — Rotate refresh token
* `DELETE /auth/delete` — Delete user account

### 2. User Profiles — `/profile`
* `GET /profile/me` — Get profile details of the logged-in user
* `PUT /profile/nickname` — Set or update nickname
* `PUT /profile/picture` — Set or update base64 profile picture
* `DELETE /profile/picture` — Remove profile picture

### 3. Movie Sessions — `/session`
* `POST /session/create` — Host creates a new movie session
* `POST /session/join` — Join a session via invite code
* `POST /session/preferences` — Submit session member preferences
* `GET /session/{id}` — Get movie session state and status
* `POST /session/{id}/recommend` — Trigger AI recommendation generation

### 4. Ratings & Interactions — `/rating`
* `POST /rating/rate` — Rate a movie (LOVE, LIKE, WATCHLIST, DISLIKE, HATE) - dynamically updates user taste vectors
* `DELETE /rating/delete` — Remove rating

---

## Database Schema

* `app_user` — User accounts with hashed password, nickname, base64 profile picture, and positive/negative taste vectors (`vector(768)`).
* `movie` — Movie catalogue with metadata (genres, runtime, tags) and semantic embeddings (`vector(768)`).
* `movie_session` — Full movie session state, lobby status, group member data, and generated recommendations.
* `room_session` — Group session with aggregated preference state.
* `rating` — Per-session rating state for users.
* `user_interaction` — Historic user interactions with movies.

---

## License

Proprietary software. See [LICENSE.md](./LICENSE.md) for details.  
© 2026 Fabian Bicca Moraes. All rights reserved.
