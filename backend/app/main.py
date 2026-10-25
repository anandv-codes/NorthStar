import logging
import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .api.routes.auth import router as auth_router
from .api.routes.chat import router as chat_router
from .api.routes.commitments import router as commitments_router
from .api.routes.notes import router as notes_router
from .api.routes.memory import router as memory_router
from .api.routes.recall import router as recall_router
from .api.routes.retrieval import router as retrieval_router
from .api.routes.summaries import router as summaries_router
from .observability import install_request_timing

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

def _cors_origins() -> list[str]:
    """Allowed browser origins, from a comma-separated ``CORS_ALLOW_ORIGINS``.

    Defaults to common local dev origins instead of ``*`` so credentialed
    requests are never silently wildcarded. Set ``CORS_ALLOW_ORIGINS=*`` to
    explicitly opt back into a wildcard (credentials are then disabled, as the
    CORS spec forbids combining ``*`` with credentials).
    """
    raw = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _warm_up_embeddings() -> None:
    """Build the embedding provider and pay its first-call handshake cost."""
    from .infrastructure.vector.embeddings import get_embeddings

    embeddings = get_embeddings()
    # One throwaway embed warms the API connection/TLS path too, so the first
    # retrieval doesn't pay the round-trip setup.
    embeddings.embed_query("warm up")


def _warm_up() -> None:
    """Build the expensive clients once, at startup, instead of per request.

    Loading the embedding model / Gemini client used to add ~7-23s to the first
    note after every restart. Failures are logged and ignored: the app should
    still boot with an unreachable external service.
    """
    if os.getenv("WARMUP_ON_STARTUP", "true").strip().lower() in {"0", "false", "no", "off"}:
        logger.info("Startup warm-up disabled (WARMUP_ON_STARTUP)")
        return

    from .infrastructure.llm.gemini_client import warm_up_llm_clients

    targets = (
        ("llm_clients", warm_up_llm_clients),
        ("embeddings", _warm_up_embeddings),
    )
    for name, warm in targets:
        started = time.perf_counter()
        try:
            warm()
        except Exception as exc:  # noqa: BLE001 - startup must not hard-fail
            logger.warning(
                "Warm-up %s failed after %d ms: %s",
                name,
                (time.perf_counter() - started) * 1000,
                exc,
            )
        else:
            logger.info(
                "Warm-up %s ready in %d ms",
                name,
                (time.perf_counter() - started) * 1000,
            )


@asynccontextmanager
async def lifespan(_: FastAPI):
    _warm_up()
    yield


app = FastAPI(title="NorthStar Backend", lifespan=lifespan)


@app.get("/health", tags=["ops"])
def health() -> dict[str, str]:
    """Liveness probe for Nginx/ALB health checks and uptime monitoring."""
    return {"status": "ok"}


@app.middleware("http")
async def unhandled_exception_guard(request, call_next):
    """Turn unhandled errors into a readable JSON 500 that keeps CORS headers.

    Registered *before* CORSMiddleware below so CORS wraps this handler. Without
    that ordering, Starlette's outermost ServerErrorMiddleware answers with a
    bare 500 and the browser reports the missing Access-Control-Allow-Origin
    header as a CORS failure, hiding the real server-side error.
    """
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


#CORS
_origins = _cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials="*" not in _origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

install_request_timing(app)

app.include_router(notes_router, prefix="/notes", tags=["notes"])
app.include_router(memory_router, tags=["memory"])
app.include_router(retrieval_router, prefix="/retrieval", tags=["retrieval"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(summaries_router, prefix="/summaries", tags=["summaries"])
app.include_router(commitments_router, prefix="/commitments", tags=["commitments"])
app.include_router(recall_router, prefix="/recall", tags=["recall"])
app.include_router(auth_router)
