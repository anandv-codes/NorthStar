import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes.auth import router as auth_router
from .api.routes.chat import router as chat_router
from .api.routes.notes import router as notes_router
from .api.routes.memory import router as memory_router
from .api.routes.recall import router as recall_router
from .api.routes.retrieval import router as retrieval_router
from .api.routes.summaries import router as summaries_router

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def _cors_origins() -> list[str]:
    """Allowed browser origins, from a comma-separated ``CORS_ALLOW_ORIGINS``.

    Defaults to common local dev origins instead of ``*`` so credentialed
    requests are never silently wildcarded. Set ``CORS_ALLOW_ORIGINS=*`` to
    explicitly opt back into a wildcard (credentials are then disabled, as the
    CORS spec forbids combining ``*`` with credentials).
    """
    raw = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(title="NorthStar Backend")


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness probe for Nginx/ALB health checks and uptime monitoring."""
    return {"status": "ok"}

#CORS
_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials="*" not in _origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes_router, prefix="/notes", tags=["notes"])
app.include_router(memory_router, tags=["memory"])
app.include_router(retrieval_router, prefix="/retrieval", tags=["retrieval"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(summaries_router, prefix="/summaries", tags=["summaries"])
app.include_router(recall_router, prefix="/recall", tags=["recall"])
app.include_router(auth_router)
