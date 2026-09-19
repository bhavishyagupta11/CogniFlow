"""
CogniFlow Backend Configuration
Handles environment variables, LLM API keys, model selections, and directory paths.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
EXTRACTED_DIR = DATA_DIR / "extracted"
MANIFEST_PATH = DATA_DIR / "manifest.json"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)
EXTRACTED_DIR.mkdir(exist_ok=True)

# Server Config
PORT = int(os.getenv("PORT", "3001"))
HOST = os.getenv("HOST", "0.0.0.0")

# LLM Config
# Priority: GEMINI_API_KEY -> GOOGLE_API_KEY -> OPENROUTER_API_KEY -> Local Ollama
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
PRIMARY_PROVIDER = os.getenv("PRIMARY_PROVIDER", "gemini")
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL") or os.getenv("GEMINI_MODEL") or os.getenv("LLM_MODEL") or "gemini-3.5-flash-lite"
SECONDARY_PROVIDER = os.getenv("SECONDARY_PROVIDER", "openrouter")
SECONDARY_MODEL = os.getenv("SECONDARY_MODEL") or os.getenv("OPENROUTER_MODEL") or "google/gemini-2.5-flash"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")

# Legacy aliases for backward compatibility
LLM_MODEL = os.getenv("LLM_MODEL", PRIMARY_MODEL)
GEMINI_MODEL = PRIMARY_MODEL
OPENROUTER_MODEL = SECONDARY_MODEL

# Application Identity & Attribution Metadata (Canonical)
APPLICATION_NAME = "CogniFlow"
DEVELOPER_NAME = "Bhavishya Gupta"
MODEL_PROVIDER_LABEL = os.getenv("MODEL_PROVIDER_LABEL", "Google Gemini")
AI_PROVIDER_NAME = "Google"

# RAG & Adaptive Pipeline Configurable Thresholds (Configurable per Mandate 2 & 3)
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "6"))
RETRIEVAL_STRATEGY = os.getenv("RETRIEVAL_STRATEGY", "hybrid").lower().strip()  # hybrid | lexical | semantic
ADAPTIVE_SIMPLE_THRESHOLD = float(os.getenv("ADAPTIVE_SIMPLE_THRESHOLD", "0.56"))
ADAPTIVE_SCORE_GAP_THRESHOLD = float(os.getenv("ADAPTIVE_SCORE_GAP_THRESHOLD", "0.05"))
RERANK_ENABLED = os.getenv("RERANK_ENABLED", "true").lower() == "true"
RERANK_SCORE_THRESHOLD = float(os.getenv("RERANK_SCORE_THRESHOLD", "0.58"))
VERIFICATION_ENABLED = os.getenv("VERIFICATION_ENABLED", "true").lower() == "true"
MAX_VERIFY_ITERATIONS = int(os.getenv("MAX_VERIFY_ITERATIONS", "1"))
MAX_RESEARCH_CONCURRENCY = int(os.getenv("MAX_RESEARCH_CONCURRENCY", "3"))
STREAM_FLUSH_INTERVAL = float(os.getenv("STREAM_FLUSH_INTERVAL", "0.03"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "86400"))

# Upload & Storage Security
UPLOAD_ACCESS_KEY = os.getenv("UPLOAD_ACCESS_KEY", "")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://cogniflow-brown.vercel.app"
    ).split(",")
    if origin.strip()
]

# Database & Object Storage Configurations (Supabase + Cloudflare R2)
DATABASE_URL = os.getenv("DATABASE_URL", "")
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower().strip()
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "cogniflow-storage")
R2_ENDPOINT = os.getenv("R2_ENDPOINT", "")
CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", os.getenv("R2_API_TOKEN", ""))
R2_API_TOKEN = CLOUDFLARE_API_TOKEN
IS_PRODUCTION = os.getenv("NODE_ENV") == "production" or bool(os.getenv("RENDER"))
if IS_PRODUCTION and not os.getenv("JWT_SECRET"):
    raise RuntimeError("CRITICAL: JWT_SECRET environment variable must be set in production mode. No hardcoded fallback allowed.")
JWT_SECRET = os.getenv("JWT_SECRET") or ("cogniflow-jwt-dev-secret-key-local-only" if not IS_PRODUCTION else "")
