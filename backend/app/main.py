import logging
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes.auth import router as auth_router
from .api.routes.chat import router as chat_router
from .api.routes.notes import router as notes_router
from .api.routes.memory import router as memory_router
from .api.routes.retrieval import router as retrieval_router

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

app = FastAPI(title="NorthStar Backend")

#CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes_router, prefix="/notes", tags=["notes"])
app.include_router(memory_router, tags=["memory"])
app.include_router(retrieval_router, prefix="/retrieval", tags=["retrieval"])
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(auth_router)
