from fastapi import FastAPI
from .handlers.notes import router as notes_router

app = FastAPI(title="NorthStar Backend")

app.include_router(notes_router, prefix="/notes", tags=["notes"])
