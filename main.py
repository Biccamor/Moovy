from fastapi import FastAPI, Request
from routers.recommendation_router import router as recommendation_router
from routers.auth_router import router as auth_router
from routers.metadata_router import router as metadata_router
from routers.preference_router import router as preference_router
from routers.session_router import router as session_router
from routers.movies_router import router as search_router
import time
import logging
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import scripts.dependencies as d
from database.main_db import create_tables
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from scripts.dependencies import limiter

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        d.load_model()
        d.load_db()
        d.load_reranker()
        create_tables()
        yield
    except Exception as e:
        logger.exception(f"Startup failed: {e}")
        raise
    finally:
        pass

app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
origins = [
    "https://groupmovie.com",
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  #TODO: zmienic przed deployem ale do testow zostawic
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    """Blokuje requesty z body > 64KB — ochrona przed DoS przez ogromny JSON."""
    MAX_BODY = 64 * 1024  # 64 KB
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=413,
            content={"detail": "Request body too large (max 64KB)"}
        )
    return await call_next(request)


app.include_router(recommendation_router)
app.include_router(auth_router)
app.include_router(metadata_router)
app.include_router(preference_router)
app.include_router(session_router)
app.include_router(search_router)

@app.get("/health")
async def health():
    return {"status": "OK", 
            "model_loaded": d.model is not None, 
            "reranker_loaded": d.reranker is not None, 
            "db_connected": d.engine is not None}

@app.get("/")
async def main():
    return "Server dziala"

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response