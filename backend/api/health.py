import os
import subprocess
from fastapi import APIRouter
from backend.services.telemetry_service import get_active_provider_info
from backend.rag.vector_store import vector_store

router = APIRouter(tags=["health"])


def _get_safe_git_commit() -> str:
    commit = os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or os.getenv("VERCEL_GIT_COMMIT_SHA")
    if commit:
        return commit[:7]
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "84ea198"


@router.get("/health")
@router.get("/api/health")
@router.get("/api")
@router.get("/api/version")
async def health_check():
    status = vector_store.get_index_status()
    provider_info = get_active_provider_info()
    return {
        "ok": True,
        "status": "online",
        "engine": "CogniFlow Python FastAPI Adaptive RAG Engine",
        "version": "2.0.0",
        "pipeline_version": "2.0.0",
        "git_commit": _get_safe_git_commit(),
        "index_ready": status.get("index_ready", True),
        "indexed_documents": status.get("indexed_documents", 0),
        "indexed_chunks": status.get("indexed_chunks", 0),
        "index_version": status.get("index_version", 1),
        "last_index_update": status.get("last_index_update", ""),
        "active_provider": provider_info["provider"],
        "model": provider_info["model"]
    }
