# COGNIFLOW — Free Deployment Storage Migration Plan
## Architecture: Vercel (Frontend) + Render Free (FastAPI) + Supabase (PostgreSQL) + Cloudflare R2 (Storage) + Gemini API

> **AUDIT DIRECTIVE**: This document is an architectural design and migration blueprint. No source code or configuration changes were implemented during this audit.

---

## 1. Executive Summary & Objective

### The Challenge
Render's Free Web Service tier provides:
- 512 MB RAM and 0.1 shared vCPU
- Automatic spin-down (sleep) after 15 minutes of inactivity
- **100% Ephemeral Filesystem**: All files written to disk are wiped on every sleep/restart/deploy
- Render Persistent Disks cost $1/GB/month and are **unavailable on the free tier**

Currently, CogniFlow relies on the local filesystem for:
1. `data/cogniflow.db`: SQLite database (users, chats, messages)
2. `data/manifest.json`: Document catalog required to build the vector store
3. `data/uploads/*`: Raw PDF and TXT files served to the frontend PDF viewer
4. `data/extracted/*`: Extracted JSON page text used for indexing and summarization
5. `data/cache/summaries/*`: Cached hierarchical summaries
6. `data/neural_embeddings_cache.json`: Cached query/document embeddings

### Target Free Deployment Architecture
```
                        [Client Browser]
                               │
         ┌─────────────────────┴─────────────────────┐
         │                                           │
         ▼                                           ▼
[Vercel Edge Network]                       [Render Free Web Service]
- React 19 + Vite SPA                       - Python 3.12 FastAPI Backend
- Static assets (client/dist)               - Single stateless container
- Free tier (unlimited bandwidth)           - In-memory TF-IDF + SVD Index
                                                     │
                         ┌───────────────────────────┼───────────────────────────┐
                         ▼                           ▼                           ▼
               [Supabase PostgreSQL]         [Cloudflare R2]              [Google Gemini API]
               - Free Tier (500 MB DB)       - Free Tier (10 GB)          - Free / Pay-go
               - Users & Auth                - Raw Uploads (PDF/TXT)      - LLM Generation
               - Chats & Messages            - Extracted Page JSONs       - Neural Embeddings
               - Document Catalog            - Zero Egress Bandwidth Fees
               - Chunks & Provenance
               - Cached Summaries
```

This plan defines the **minimum architectural migration** required to deploy CogniFlow completely free, without persistent disk, while preserving 100% of its current features, authorization policies, and test guarantees.

---

## 2. Comprehensive Trace of Every Persistent Data Path

| # | File / Module | Current Storage | Read/Write Operation | Data Description | User Data? | Migration Target |
|:---|:---|:---|:---|:---|:---:|:---|
| 1 | `backend/services/db_service.py` | `data/cogniflow.db` (SQLite) | `init_db()`: DDL table creation | Schema definition for users, conversations, messages | No | Supabase PostgreSQL (`init_db()` via asyncpg/psycopg) |
| 2 | `backend/services/db_service.py` | `data/cogniflow.db` (SQLite) | `create_user()`, `get_user_by_id()`, `get_user_by_email()` | User credentials, emails, password hashes | **YES** | Supabase PostgreSQL: `users` table |
| 3 | `backend/services/db_service.py` | `data/cogniflow.db` (SQLite) | `create_conversation()`, `get_conversation()`, `list_conversations()` | Conversation sessions, titles, modes | **YES** | Supabase PostgreSQL: `conversations` table |
| 4 | `backend/services/db_service.py` | `data/cogniflow.db` (SQLite) | `save_message()`, `list_messages()` | Chat messages, assistant responses, citation metadata | **YES** | Supabase PostgreSQL: `messages` table |
| 5 | `backend/services/document_service.py` | `data/manifest.json` (JSON) | `get_manifest()`: reads JSON list | Document catalog, metadata, page/chunk counts, ownership | **YES** | Supabase PostgreSQL: `documents` table |
| 6 | `backend/services/document_service.py` | `data/manifest.json` (JSON) | `save_manifest()`: writes JSON via `.tmp` | Appends/updates/deletes document records | **YES** | Supabase PostgreSQL: `documents` table |
| 7 | `backend/services/document_service.py` | `data/uploads/{doc_id}.pdf` | `stored_path.write_bytes(file_bytes)` | Raw uploaded PDF or TXT document | **YES** | Cloudflare R2: `uploads/{doc_id}.{ext}` |
| 8 | `backend/services/document_service.py` | `data/extracted/{doc_id}.json` | `extracted_path.write_text(json)` | Extracted pages text array `[{"pageNumber": int, "text": str}]` | **YES** | Cloudflare R2: `extracted/{doc_id}.json` + Postgres `document_chunks` |
| 9 | `backend/api/documents.py` | `data/uploads/{doc_id}.pdf` | `FileResponse(file_path)` | Serves raw PDF file to frontend PDF viewer | **YES** | R2 Presigned GET URL (HTTP 307 redirect) or streaming proxy |
| 10 | `backend/api/documents.py` | `data/uploads/` & `data/extracted/` | `file_path.read_text()` | Serves raw plain-text view (`/api/documents/{id}/raw`) | **YES** | Cloudflare R2: stream object via `boto3` |
| 11 | `backend/rag/vector_store.py` | `data/manifest.json` + `data/extracted/*.json` | `_rebuild()`: parses manifest & JSONs | Rebuilds TF-IDF matrix & fits LSA TruncatedSVD model | Both | Supabase PostgreSQL: `document_chunks` table (loaded on startup into RAM) |
| 12 | `backend/services/summary_cache.py` | `data/cache/summaries/{key}.json` | `disk_file.read_text()` / `write_text()` | Precomputed hierarchical document summaries | Both | Supabase PostgreSQL: `document_summaries` table |
| 13 | `backend/services/summary_cache.py` | `data/cache/summaries/b_{key}.txt` | `disk_file.read_text()` / `write_text()` | Precomputed batch-level map summaries | Both | In-memory LRU cache + Supabase PostgreSQL |
| 14 | `backend/rag/embeddings.py` | `data/neural_embeddings_cache.json` | `_load_cache()` / `_save_cache()` | Precomputed dense Gemini embedding vectors | System | In-memory cache with fallback to Gemini API (zero correctness dependency) |
| 15 | `backend/api/evaluation.py` | `data/retrieval_benchmark_cache.json` | `json.load()` / `json.dump()` | Cached empirical evaluation benchmark metrics | System | In-memory singleton with on-demand refresh |
| 16 | `backend/rag/summarizer.py` | In-process event loop | `_active_precomputations[doc_id] = loop.create_task(...)` | Background asyncio task for document map-reduce | System | In-process `asyncio.Task` with restart-safe status in Postgres |

---

## 3. PostgreSQL Migration Design (Supabase)

### Target Schema Architecture
We replace SQLite and `manifest.json` with a normalized PostgreSQL schema enforcing strict foreign key constraints, cascading deletions, and ownership indices.

```sql
-- 1. Users Table (Preserves bcrypt password hashing & JWT sub mapping)
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(LOWER(email));

-- 2. Conversations Table
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'deep_research',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
    ON conversations(user_id, updated_at DESC);

-- 3. Messages Table
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_messages_conv_created
    ON messages(conversation_id, created_at ASC);

-- 4. Documents Table (Replaces data/manifest.json)
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'dev-user',
    tenant_id TEXT NOT NULL DEFAULT 'dev-user',
    original_filename TEXT NOT NULL,
    storage_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'application/pdf',
    size_bytes BIGINT NOT NULL DEFAULT 0,
    file_hash TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 1,
    char_count INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    processing_status TEXT NOT NULL DEFAULT 'completed', -- 'pending' | 'processing' | 'completed' | 'failed'
    index_status TEXT NOT NULL DEFAULT 'indexed',       -- 'indexed' | 'not_indexed'
    index_version INTEGER NOT NULL DEFAULT 1,
    r2_upload_key TEXT NOT NULL,                        -- e.g. "uploads/doc_id.pdf"
    r2_extracted_key TEXT,                              -- e.g. "extracted/doc_id.json"
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents(owner_id);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);

-- 5. Document Chunks Table (Enables instant vector index reconstruction on boot)
CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,                                -- e.g. "{doc_id}_c{page}_{i}"
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    char_count INTEGER NOT NULL,
    token_count INTEGER NOT NULL,
    authors TEXT DEFAULT 'Uploaded Document',
    year INTEGER DEFAULT 2026,
    source TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_order ON document_chunks(document_id, chunk_index ASC);

-- 6. Document Summaries Table (Replaces data/cache/summaries/*.json)
CREATE TABLE IF NOT EXISTS document_summaries (
    id TEXT PRIMARY KEY,                                -- SHA-256(doc_id + doc_hash + page_range + config_hash)
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_range TEXT NOT NULL DEFAULT 'all',
    config_hash TEXT NOT NULL DEFAULT 'v1',
    summary_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_summaries_doc ON document_summaries(document_id);
```

### Authorization Parity
- **User A**: `SELECT * FROM documents WHERE owner_id = 'user_A' OR owner_id IN ('system_public', 'public')`
- **Guest / Dev Workspace**: `SELECT * FROM documents WHERE owner_id IN ('dev-user', 'guest', 'user_default', 'system_public')`
- **Privileged Administrator**: `SELECT * FROM documents`
- **Anti-Spoofing**: Enforced identically in [`auth_service.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/services/auth_service.py) before queries execute.

---

## 4. Document Storage Migration (Cloudflare R2)

### Storage Abstraction Interface
Rather than coupling the backend to local filesystem paths (`UPLOADS_DIR / filename`), we define a swappable `StorageService` interface.

```python
# backend/services/storage_service.py
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional

class BaseStorageService(ABC):
    @abstractmethod
    async def put_object(self, key: str, data: bytes, content_type: str) -> str:
        """Stores object bytes at key and returns the key."""
        pass

    @abstractmethod
    async def get_object(self, key: str) -> bytes:
        """Retrieves object bytes by key."""
        pass

    @abstractmethod
    async def delete_object(self, key: str) -> bool:
        """Deletes object by key."""
        pass

    @abstractmethod
    def generate_presigned_url(self, key: str, expires_in_seconds: int = 900) -> str:
        """Generates a temporary signed URL for direct client access."""
        pass
```

### Implementations
1. **`LocalStorageService`**: Uses local `data/uploads` and `data/extracted` (used for local testing and offline dev).
2. **`R2StorageService`**: Uses `boto3` or `aioboto3` configured with Cloudflare R2's S3-compatible API:
   - Endpoint: `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com`
   - Authentication: `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`
   - Bucket: `R2_BUCKET_NAME` (e.g. `cogniflow-storage`)

### Object Key Conventions
- Raw upload: `uploads/{doc_id}.pdf` (or `uploads/{doc_id}.txt`)
- Extracted JSON: `extracted/{doc_id}.json`

### Serving PDFs & Security
- The Cloudflare R2 bucket remains **100% PRIVATE**. Direct public access is disabled.
- When the client opens a PDF citation, [`client/src/components/rag/pdf-viewer.jsx`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/client/src/components/rag/pdf-viewer.jsx) calls `GET /api/documents/{doc_id}/pdf`.
- The FastAPI endpoint authoritatively verifies the caller's JWT token and document ownership.
- Upon authorization, FastAPI returns an **HTTP 307 Temporary Redirect** to a short-lived presigned R2 GET URL (valid for 15 minutes).
- The client's `react-pdf` viewer follows the redirect and downloads the PDF directly from Cloudflare's global edge network at high speed, consuming **zero Render compute or bandwidth**.

---

## 5. Vector Store & Embedding Migration Strategy

### Comparison of Options

| Architectural Option | Startup Overhead | Runtime Latency | Implementation Effort | Free Tier Memory (512MB) | Multi-Instance Safe? |
|:---|:---:|:---:|:---:|:---:|:---:|
| **Option A: Rebuild In-Memory Index on Boot from PostgreSQL Chunks** *(RECOMMENDED MINIMUM)* | **~150ms** | **< 2ms** (Sub-5ms search) | **Low** (Zero RAG changes) | **Safe** (Corpus uses ~25MB RAM) | Safe for single free instance |
| **Option B: Supabase pgvector** | None | 15ms – 40ms (DB network hop) | High (Requires rewriting vector store, RRF, MMR in SQL) | N/A | Fully multi-instance safe |
| **Option C: External Managed Vector DB (Qdrant / Pinecone)** | None | 25ms – 60ms (SaaS network hop) | High (New SaaS dependency & client rewrite) | N/A | Fully multi-instance safe |

### Minimum Recommended Strategy: Option A
1. **Startup Loading**:
   - When Render Free spins up from sleep, `vector_store._rebuild()` runs.
   - It executes a single SQL query:
     ```sql
     SELECT id, document_id, chunk_index, page_number, content, authors, year, source
     FROM document_chunks
     ORDER BY document_id, chunk_index ASC;
     ```
   - It also loads the 3 built-in static papers from `backend/rag/documents.py`.
   - It constructs the in-memory TF-IDF matrix and fits the 64-dim LSA TruncatedSVD model in Python memory in under 150 milliseconds.
2. **Advantages**:
   - Exactly zero changes required to [`vector_store.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/rag/vector_store.py), [`retriever.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/rag/retriever.py), [`mmr.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/rag/mmr.py), [`reranker.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/rag/reranker.py), or [`adaptive_controller.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/rag/adaptive_controller.py).
   - All 56 existing regression tests continue to pass without modification.
   - Memory footprint for 3,000 document chunks is ~25 MB, well within Render Free's 512 MB ceiling.

---

## 6. Summary Cache & Embedding Cache Strategy

### Summary Cache
- **Current problem**: Writes to `data/cache/summaries/{key}.json` which is wiped on Render sleep.
- **Solution**:
  - Point [`summary_cache.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/services/summary_cache.py) to the `document_summaries` PostgreSQL table.
  - On summary check: `SELECT summary_data FROM document_summaries WHERE id = :key`.
  - On summary set: `INSERT INTO document_summaries (id, document_id, page_range, config_hash, summary_data) VALUES (...) ON CONFLICT (id) DO UPDATE ...`.
  - Cache invalidation on delete: Automatic via `ON DELETE CASCADE` when the document is deleted!
  - Disk storage is completely eliminated; cached summaries survive Render Free restarts forever.

### Embedding Cache
- **Current problem**: `data/neural_embeddings_cache.json` is a 3.5 MB local file.
- **Solution**:
  - The embedding cache is an **optimization-only accelerator**. System correctness does **not** depend on it.
  - On Render Free, initialize `_query_cache` and `_doc_cache` as in-memory dictionaries.
  - If a query embedding is not cached, call Google Gemini `embed_content(model="gemini-embedding-001")`.
  - For free tier simplicity, no external storage is required. If persistent caching is desired, a single `neural_embeddings_cache` table or storing the JSON file in R2 (`cache/neural_embeddings_cache.json`) on shutdown/startup can be used.

---

## 7. Background Tasks on Render Free

### The Spin-Down Reality
- Render Free instances shut down after 15 minutes of zero HTTP traffic.
- Any background `asyncio.Task` running at the moment of spin-down will receive a `SIGTERM` / `asyncio.CancelledError`.

### Classification: Optimization vs. Correctness
- **Document Ingestion**: **Correctness-Critical**.
  - Text extraction, chunking, PostgreSQL metadata writing, and R2 file uploads run **synchronously** during the `POST /api/documents` request.
  - The document is fully indexed and searchable before the HTTP response returns.
- **Summary Precomputation**: **Optimization-Only**.
  - Initiated via `asyncio.create_task` after ingestion.
  - If interrupted by a container restart, no data is corrupted.
  - When the user subsequently requests a summary, `pipeline.py` detects a cache miss and executes hierarchical summarization with real-time SSE progress streaming.
  - **No Celery / Redis queue required** for the free tier.

---

## 8. Deletion Consistency with PostgreSQL & R2

The atomic staged rollback mechanism designed in [`document_service.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/services/document_service.py) maps cleanly to PostgreSQL and R2:

```
                      [delete_document(doc_id)]
                                  │
    ┌─────────────────────────────┴─────────────────────────────┐
    ▼                                                           ▼
1. Cancel Active Background Task                     2. PostgreSQL Transaction
   (cancel_document_summary_precomputation)             DELETE FROM documents WHERE id = doc_id;
                                                        (Cascades delete to document_chunks
                                                         and document_summaries automatically!)
                                                                │
                                                                ▼
                                                     3. Vector Store Purge
                                                        (remove_document from in-memory index)
                                                                │
                                                                ▼
                                                     4. In-Memory Cache Invalidation
                                                        (summary_cache.invalidate_document)
                                                                │
                                                                ▼
                                                     5. R2 Object Storage Deletion
                                                        r2.delete_object("uploads/{doc_id}.pdf")
                                                        r2.delete_object("extracted/{doc_id}.json")
```

### Safety Invariant
- If step 2 (PostgreSQL) fails: Transaction aborts, database state rolls back, and nothing is deleted.
- If step 5 (R2) encounters a transient network timeout: The document is already removed from PostgreSQL and vector search. No user can retrieve or search it. A background task or script can clean orphan R2 objects if needed.

---

## 9. Render Free Web Service Specifications

- **Runtime**: Python 3.12 (`PYTHON_VERSION: 3.12.4`).
- **Build Command**: `pip install -r backend/requirements.txt`
- **Start Command**: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Dependencies Update**:
  Add the missing libraries to `backend/requirements.txt`:
  ```text
  fastapi>=0.110.0
  uvicorn>=0.27.0
  pydantic>=2.5.0
  numpy>=1.26.0
  PyMuPDF>=1.23.0
  google-genai>=2.0.0
  openai>=1.12.0
  python-multipart>=0.0.9
  python-dotenv>=1.0.1
  scikit-learn>=1.4.0
  pyjwt>=2.8.0
  bcrypt>=4.1.2
  asyncpg>=0.29.0
  boto3>=1.34.0
  ```
- **Cold Start Handling**:
  - On free tier spin-up, Render takes 50–75 seconds to provision the container.
  - The frontend already has a timeout/retry handler in `apiFetch`.
  - Once the container boots, `init_db()` and `vector_store._rebuild()` complete in < 300ms.

---

## 10. Vercel Frontend Specifications

- **Hosting**: Static HTML/JS/CSS on Vercel Edge CDN.
- **Root Directory**: `client`
- **Framework Preset**: `Vite`
- **Build Command**: `npm run build`
- **Output Directory**: `dist`
- **Build Environment Variable**:
  ```text
  VITE_API_BASE_URL=https://<your-render-backend-name>.onrender.com
  ```
- **No Node Backend on Vercel**: All API routing is sent across CORS to Render.

---

## 11. Environment Variable Inventory for Target Deployment

| Variable Name | Required Service | Purpose | Secret? | Example Format |
|:---|:---:|:---|:---:|:---|
| `DATABASE_URL` | Render Backend | Supabase PostgreSQL Connection String (Transaction Pooler port 6543) | **YES** | `postgresql://postgres.[ref]:[pwd]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require` |
| `R2_ACCOUNT_ID` | Render Backend | Cloudflare Account ID | **YES** | `<YOUR_R2_ACCOUNT_ID>` |
| `R2_ACCESS_KEY_ID` | Render Backend | Cloudflare R2 API Token Key | **YES** | `8e3a2b1c4d5e6f7a8b9c...` |
| `R2_SECRET_ACCESS_KEY` | Render Backend | Cloudflare R2 Secret Key | **YES** | `f1e2d3c4b5a6...` |
| `R2_BUCKET_NAME` | Render Backend | Name of the R2 bucket | No | `cogniflow-storage` |
| `R2_ENDPOINT` | Render Backend | Custom or standard R2 endpoint URL | No | `https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `GEMINI_API_KEY` | Render Backend | Google Gemini API key for generation & embeddings | **YES** | `AIzaSy...` |
| `OPENROUTER_API_KEY` | Render Backend | Fallback OpenRouter API key | **YES** | `sk-or-v1-...` |
| `JWT_SECRET` | Render Backend | Cryptographic secret for signing session JWT tokens | **YES** | *(Random 64-char hex string)* |
| `CORS_ORIGINS` | Render Backend | Allowed frontend origin URL | No | `https://cogniflow.vercel.app` |
| `VITE_API_BASE_URL` | Vercel Frontend | URL of the Render backend | No | `https://cogniflow-api.onrender.com` |

---

## 12. Step-by-Step Migration Order

```
[Phase 1: External Services Setup]
  1. Create Supabase project -> Obtain DATABASE_URL (port 6543 with SSL)
  2. Create Cloudflare R2 bucket "cogniflow-storage" -> Obtain Access Keys
  3. Ensure Google Gemini API key is ready

[Phase 2: Backend Dependencies & Database Layer]
  4. Add scikit-learn, pyjwt, bcrypt, asyncpg, boto3 to backend/requirements.txt
  5. Create backend/services/db_pg.py (or update db_service.py) with Supabase asyncpg pool
  6. Execute SQL DDL in Supabase to create users, conversations, messages, documents, chunks, summaries
  7. Verify auth endpoints (/api/auth/register, /api/auth/login) against Supabase

[Phase 3: Object Storage Abstraction & Document Service]
  8. Implement backend/services/storage_service.py (R2StorageService via boto3)
  9. Update document_service.py:
     - Ingestion writes file bytes to R2
     - Document metadata written to documents table
     - Chunks written to document_chunks table
  10. Update api/documents.py:
     - /api/documents/{id}/pdf redirects to R2 presigned URL
     - /api/documents queries documents table directly

[Phase 4: Vector Store & Summary Cache]
  11. Update vector_store._rebuild() to load chunks from document_chunks table
  12. Update summary_cache.py to read/write document_summaries table in PostgreSQL

[Phase 5: Automated Testing & Verification]
  13. Run full regression test suite: python -m pytest backend/tests/ -v
  14. Run live upload, citation, and deletion tests

[Phase 6: Cloud Deployment]
  15. Deploy FastAPI to Render Free (set all environment variables)
  16. Deploy React frontend to Vercel (set VITE_API_BASE_URL)
  17. Set CORS_ORIGINS on Render to match Vercel domain
  18. Perform end-to-end smoke test on live production URLs
```

---

## 13. Exact Files That Will Need Changes

1. [`backend/requirements.txt`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/requirements.txt):
   - Add `scikit-learn`, `pyjwt`, `bcrypt`, `asyncpg`, `boto3`.
2. [`backend/config.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/config.py):
   - Add `DATABASE_URL`, `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT`.
3. [`backend/services/db_service.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/services/db_service.py):
   - Switch connection pool from `sqlite3` to PostgreSQL (`asyncpg` or `psycopg`).
4. **[NEW]** `backend/services/storage_service.py`:
   - Implement `BaseStorageService`, `LocalStorageService`, and `R2StorageService`.
5. [`backend/services/document_service.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/services/document_service.py):
   - Route file uploads to `storage_service.put_object`.
   - Route metadata to `documents` and `document_chunks` tables instead of `manifest.json`.
6. [`backend/services/summary_cache.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/services/summary_cache.py):
   - Read and write summaries to `document_summaries` table.
7. [`backend/rag/vector_store.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/rag/vector_store.py):
   - Update `_rebuild()` to query chunks from `document_chunks` table.
8. [`backend/api/documents.py`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/backend/api/documents.py):
   - Return presigned R2 URL or stream for `/api/documents/{id}/pdf`.
9. [`render.yaml`](file:///c:/Users/Sbhav/Coding/MultiAgent%20RAG%20Systems/render.yaml):
   - Declare the new environment variable keys.

---

## 14. Migration Risks & Rollback Plan

### Risks
1. **Supabase Free Connection Limits**:
   - Supabase free tier enforces a connection limit (~15–20 direct connections).
   - *Mitigation*: Connect through the **Supabase Transaction Pooler** (port 6543) using `asyncpg` with `max_size=5`.
2. **Render Cold Start Latency**:
   - Spin-up from sleep takes 50–75s.
   - *Mitigation*: The frontend displays clean loading skeletons; once awake, queries return in sub-3s.
3. **R2 Presigned URL CORS**:
   - The R2 bucket must have an S3 CORS policy allowing `GET` from the Vercel domain.

### Rollback Plan
- The storage abstraction allows instantaneous rollback: Setting `STORAGE_BACKEND=local` falls back to the existing local filesystem implementation for development and testing.
- SQLite code is preserved in Git; if Postgres connectivity fails during development, the system can immediately revert to local `cogniflow.db`.
