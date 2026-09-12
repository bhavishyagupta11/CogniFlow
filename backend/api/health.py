"""
Health Check Router
"""

from fastapi import APIRouter
from backend.services.telemetry_service import get_active_provider_info
from backend.rag.vector_store import vector_store

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/api/health")
@router.get("/api")
async def health_check():
    status = vector_store.get_index_status()
    provider_info = get_active_provider_info()
    return {
        "ok": True,
        "status": "online",
        "engine": "CogniFlow Python FastAPI Adaptive RAG Engine",
        "version": "2.0.0",
        "index_ready": status.get("index_ready", True),
        "indexed_documents": status.get("indexed_documents", 0),
        "indexed_chunks": status.get("indexed_chunks", 0),
        "index_version": status.get("index_version", 1),
        "last_index_update": status.get("last_index_update", ""),
        "active_provider": provider_info["provider"],
        "model": provider_info["model"]
    }
