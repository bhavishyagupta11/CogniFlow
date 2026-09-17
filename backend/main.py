"""
CogniFlow Python FastAPI Backend Application
High-Performance, Sub-3s RAG Engine matching the exact React Frontend contracts.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.config import PORT, HOST, CORS_ORIGINS
from backend.services.db_service import init_db
from backend.api.health import router as health_router
from backend.api.auth import router as auth_router
from backend.api.chats import router as chats_router
from backend.api.chat import router as chat_router
from backend.api.documents import router as documents_router
from backend.api.evaluation import router as evaluation_router

# Initialize SQLite persistence tables & indexes
init_db()

app = FastAPI(
    title="CogniFlow Adaptive RAG Engine API",
    description="Evidence-grounded high-speed multi-agent RAG backend",
    version="2.0.0"
)

# Enable CORS for React + Vite frontend. In production, set CORS_ORIGINS to your
# Vercel URL(s), comma-separated.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Session-ID"]
)


@app.middleware("http")
async def guest_session_header_middleware(request: Request, call_next):
    response = await call_next(request)
    session_id = getattr(request.state, "session_id", None)
    if session_id and "X-Session-ID" not in response.headers:
        response.headers["X-Session-ID"] = session_id
    return response

# Mount Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chats_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(evaluation_router)


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
