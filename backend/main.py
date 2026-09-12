"""
CogniFlow Python FastAPI Backend Application
High-Performance, Sub-3s RAG Engine matching the exact React Frontend contracts.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from backend.config import PORT, HOST
from backend.api.health import router as health_router
from backend.api.chat import router as chat_router
from backend.api.documents import router as documents_router
from backend.api.evaluation import router as evaluation_router

app = FastAPI(
    title="CogniFlow Adaptive RAG Engine API",
    description="Evidence-grounded high-speed multi-agent RAG backend",
    version="2.0.0"
)

# Enable CORS for React + Vite frontend (port 5173, port 3000, and preview ports)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"]
)

# Mount Routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(documents_router)
app.include_router(evaluation_router)


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
