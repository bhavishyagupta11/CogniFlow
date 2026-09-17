# CogniFlow Backend API Reference

This document provides a technical API reference for the CogniFlow backend service implemented in FastAPI.

---

## 1. API Overview

### Base URLs

- **Local Development**: `http://localhost:3001` (Vite frontend dev server proxies `/api` requests to `http://127.0.0.1:3001`)
- **Production Deployment**: `https://<backend-service-name>.onrender.com` (configured via `render.yaml`)

### Architecture

The backend exposes two interaction paradigms:

1. **Synchronous REST API**: Standard HTTP endpoints for user authentication, conversation session management, document cataloging, binary file ingestion, document reindexing, and evaluation telemetry. All REST endpoints consume and emit `application/json`, with the exception of multipart file uploads and binary PDF streams.
2. **Server-Sent Events (SSE) Streaming**: Real-time token and pipeline execution event streaming via `POST /api/chat` over a persistent HTTP connection (`text/event-stream`).

### Authentication Model

The service employs a dual-mode identity resolution system:

- **Authenticated Users**: Validated via standard HTTP Bearer tokens (`Authorization: Bearer <TOKEN>`) containing a cryptographically signed JSON Web Token (HS256). All user assets, conversations, and documents are strictly scoped to the authenticated user ID.
- **Guest / Development Workspaces**: Unauthenticated callers default safely to a sandboxed workspace (`dev-user`). Anti-spoofing validations prevent unauthenticated callers from impersonating registered user accounts or claiming administrative privileges.

---

## 2. Authentication API

All authentication routes are mounted under the `/api/auth` prefix.

### Register User

Creates a new user account and returns an authenticated JWT session token.

- **Method**: `POST`
- **Path**: `/api/auth/register`
- **Authentication**: None (Public)
- **Request Headers**:
  - `Content-Type: application/json`
- **Request Body Schema** ([`AuthRegisterRequest`](file:///backend/models.py#L224-L228)):
  ```json
  {
    "name": "string",
    "email": "string",
    "password": "string",
    "confirm_password": "string (optional)"
  }
  ```
- **Validation Rules**:
  - `name`: Required, non-empty string.
  - `email`: Required, valid RFC 5322 email format. Converted to lowercase.
  - `password`: Required, minimum 6 characters, maximum 128 characters.
  - `confirm_password`: Optional; if provided, must match `password` exactly.
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "token": "<TOKEN>",
    "user": {
      "id": "user_<UUID>",
      "email": "engineer@example.com",
      "name": "Alex Mercer",
      "createdAt": "2026-09-17T12:00:00+00:00"
    }
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: Validation failure (empty name, invalid email syntax, password under 6 characters, or passwords do not match).
  - `409 Conflict`: An account with the supplied email address already exists.

### Login

Authenticates existing user credentials and returns a JWT session token.

- **Method**: `POST`
- **Path**: `/api/auth/login`
- **Authentication**: None (Public)
- **Request Headers**:
  - `Content-Type: application/json`
- **Request Body Schema** ([`AuthLoginRequest`](file:///backend/models.py#L231-L234)):
  ```json
  {
    "email": "string",
    "password": "string"
  }
  ```
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "token": "<TOKEN>",
    "user": {
      "id": "user_<UUID>",
      "email": "engineer@example.com",
      "name": "Alex Mercer",
      "createdAt": "2026-09-17T12:00:00+00:00"
    }
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: Missing email or password.
  - `401 Unauthorized`: Invalid email or password. Returns a generic message to prevent account enumeration.

### Logout

Signals user session termination. Tokens are stateless and invalidated client-side by deleting the stored token.

- **Method**: `POST`
- **Path**: `/api/auth/logout`
- **Authentication**: None
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "message": "Successfully logged out."
  }
  ```

### Verify Identity (`/me`)

Validates the caller's JWT bearer token and returns the current user profile.

- **Method**: `GET`
- **Path**: `/api/auth/me`
- **Authentication**: Required (`Authorization: Bearer <TOKEN>`)
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "user": {
      "id": "user_<UUID>",
      "email": "engineer@example.com",
      "name": "Alex Mercer"
    }
  }
  ```
- **Error Responses**:
  - `401 Unauthorized`: Missing `Authorization` header, invalid token signature, expired token session, or user account not found.

---

## 3. Chat / Conversation API

### Stream Chat Query

Executes the multi-agent RAG pipeline and streams lifecycle events, retrieval metadata, and generative token deltas via Server-Sent Events (SSE).

- **Method**: `POST`
- **Path**: `/api/chat`
- **Authentication**: Optional (supports `Authorization: Bearer <TOKEN>` or fallback `x-user-id` header; defaults to `dev-user`)
- **Request Headers**:
  - `Content-Type: application/json`
  - `Authorization: Bearer <TOKEN>` (optional)
  - `x-user-id: <USER_ID>` (optional)
- **Request Body Schema** ([`ChatQueryRequest`](file:///backend/models.py#L10-L19)):
  ```json
  {
    "question": "string",
    "message": "string (optional alias for question)",
    "query": "string (optional alias for question)",
    "mode": "adaptive_rag",
    "document_id": "<DOCUMENT_ID> (optional)",
    "conversation_id": "<CONVERSATION_ID> (optional)",
    "conversationId": "<CONVERSATION_ID> (optional alias)",
    "sync": false
  }
  ```
- **Parameter Specifications**:
  - `question` / `message` / `query`: Input query text (required, 1 to 1,500 characters).
  - `mode`: Execution mode. Supported values:
    - `"adaptive_rag"`: Adaptive retrieval routing with dynamic complexity analysis (default).
    - `"fast"`: Low-latency direct hybrid retrieval skipping critic and rewrite stages.
    - `"deep_research"`: Multi-step query decomposition, reranking, and critique verification.
    - `"general_chat"`: Direct LLM generation without document retrieval or citations.
  - `document_id`: Optional UUID string restricting retrieval scope to a single document.
  - `conversation_id` / `conversationId`: Optional UUID string identifying the conversation session. When provided for authenticated users, the conversation session and message history are automatically persisted.
  - `sync`: Optional boolean flag for synchronous execution bypass (default `false`).
- **Response Headers**:
  - `Content-Type: text/event-stream; charset=utf-8`
  - `Cache-Control: no-cache, no-transform`
  - `Connection: keep-alive`
  - `X-Accel-Buffering: no`
  - `Content-Encoding: none`
- **Streaming Behavior**:
  - Immediately dispatches a `: connected\n\n` SSE comment chunk to establish the transport stream without proxy buffering delay.
  - Dispatches discrete JSON events prefixed with `data: ` and terminated with `\n\n`.
  - Dispatches `token` and `text_delta` chunks in real-time as the LLM streams output.
  - Upon completion of the SSE stream (`pipeline_complete`), full assistant messages and execution telemetry are saved asynchronously to PostgreSQL without adding latency to the client stream.
- **Error Responses**:
  - `400 Bad Request`: Missing question field, or question length exceeds 1,500 characters.

### List Conversations

Retrieves all conversations belonging to the authenticated user, ordered by most recently updated.

- **Method**: `GET`
- **Path**: `/api/chats`
- **Authentication**: Required (`Authorization: Bearer <TOKEN>`)
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "conversations": [
      {
        "id": "<CONVERSATION_ID>",
        "user_id": "user_<UUID>",
        "title": "Data Structures Analysis",
        "mode": "adaptive_rag",
        "created_at": "2026-09-17T12:00:00+00:00",
        "updated_at": "2026-09-17T12:05:00+00:00",
        "message_count": 4
      }
    ]
  }
  ```
- **Error Responses**:
  - `401 Unauthorized`: Missing or invalid bearer token.

### Create Conversation

Creates a new conversation session assigned to the authenticated user.

- **Method**: `POST`
- **Path**: `/api/chats`
- **Authentication**: Required (`Authorization: Bearer <TOKEN>`)
- **Request Body Schema** ([`ConversationCreateRequest`](file:///backend/models.py#L249-L253)):
  ```json
  {
    "id": "<CONVERSATION_ID> (optional)",
    "title": "string (optional, default 'New Mission')",
    "mode": "string (optional, default 'deep_research')"
  }
  ```
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "conversation": {
      "id": "<CONVERSATION_ID>",
      "user_id": "user_<UUID>",
      "title": "Distributed Systems Notes",
      "mode": "deep_research",
      "created_at": "2026-09-17T12:00:00+00:00",
      "updated_at": "2026-09-17T12:00:00+00:00"
    }
  }
  ```

### Get Conversation Details

Retrieves a conversation and its complete chronological message history. Strictly verifies ownership.

- **Method**: `GET`
- **Path**: `/api/chats/{conv_id}`
- **Authentication**: Required (`Authorization: Bearer <TOKEN>`)
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "conversation": {
      "id": "<CONVERSATION_ID>",
      "user_id": "user_<UUID>",
      "title": "Distributed Systems Notes",
      "mode": "deep_research",
      "created_at": "2026-09-17T12:00:00+00:00",
      "updated_at": "2026-09-17T12:05:00+00:00",
      "messages": [
        {
          "id": "msg_<UUID>",
          "conversation_id": "<CONVERSATION_ID>",
          "user_id": "user_<UUID>",
          "role": "user",
          "content": "Explain B-Tree rebalancing.",
          "metadata": null,
          "created_at": "2026-09-17T12:01:00+00:00"
        },
        {
          "id": "msg_<UUID>",
          "conversation_id": "<CONVERSATION_ID>",
          "user_id": "user_<UUID>",
          "role": "assistant",
          "content": "B-Tree rebalancing occurs when...",
          "metadata": {
            "sources": [],
            "citations": [],
            "steps": [],
            "totalDurationMs": 1420
          },
          "created_at": "2026-09-17T12:01:02+00:00"
        }
      ]
    }
  }
  ```
- **Error Responses**:
  - `401 Unauthorized`: Missing or invalid bearer token.
  - `404 Not Found`: Conversation does not exist or belongs to another user.

### Delete Conversation

Permanently deletes a conversation and all its associated messages.

- **Method**: `DELETE`
- **Path**: `/api/chats/{conv_id}`
- **Authentication**: Required (`Authorization: Bearer <TOKEN>`)
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "message": "Conversation successfully deleted."
  }
  ```
- **Error Responses**:
  - `401 Unauthorized`: Missing or invalid bearer token.
  - `404 Not Found`: Conversation does not exist or belongs to another user.

### Append Message

Appends an individual message to an existing conversation. If the conversation does not exist, it is created automatically. If the conversation title is default (`"New Mission"`), it is automatically updated using the initial text of the user message.

- **Method**: `POST`
- **Path**: `/api/chats/{conv_id}/messages`
- **Authentication**: Required (`Authorization: Bearer <TOKEN>`)
- **Request Body Schema** ([`MessageSaveRequest`](file:///backend/models.py#L255-L260)):
  ```json
  {
    "id": "string (optional UUID)",
    "role": "user",
    "content": "string",
    "metadata": { "optional": "telemetry or citation dictionary" }
  }
  ```
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "message": {
      "id": "msg_<UUID>",
      "conversation_id": "<CONVERSATION_ID>",
      "user_id": "user_<UUID>",
      "role": "user",
      "content": "Summarize Section 3.",
      "metadata": {},
      "created_at": "2026-09-17T12:00:00+00:00"
    }
  }
  ```
- **Error Responses**:
  - `401 Unauthorized`: Missing or invalid bearer token.
  - `404 Not Found`: Failed to persist message.

---

## 4. Document API

Mounted under `/api/documents`.

### List Documents

Lists active documents in the knowledge base according to caller authorization.

- **Method**: `GET`
- **Path**: `/api/documents`
- **Authentication**: Optional (supports `Authorization: Bearer <TOKEN>` or `x-user-id` header)
- **Authorization Scoping**:
  - **Administrators**: Returns all documents across the entire corpus.
  - **Authenticated Users**: Returns documents owned by the caller (`owner_id == identity.user_id`) plus global public documents (`owner_id in ["public", "system_public"]`).
  - **Guest Callers**: Returns documents assigned to the guest workspace (`owner_id in ["dev-user", "guest"]`) plus global public documents.
- **Success Response** (`200 OK`):
  Array of [`DocumentItem`](file:///backend/models.py#L39-L56) objects:
  ```json
  [
    {
      "id": "<DOCUMENT_ID>",
      "filename": "<DOCUMENT_ID>.pdf",
      "originalFilename": "Operating_Systems_Concepts.pdf",
      "mimeType": "application/pdf",
      "size": 4194304,
      "uploadedAt": "2026-09-17T10:00:00+00:00",
      "lastModified": "2026-09-17T10:00:00+00:00",
      "pageCount": 42,
      "chunkCount": 85,
      "chunkIds": ["<CHUNK_ID_1>", "<CHUNK_ID_2>"],
      "processingStatus": "completed",
      "indexStatus": "indexed",
      "ownerId": "user_<UUID>",
      "owner_id": "user_<UUID>",
      "hash": "a1b2c3d4e5f6...",
      "error": null
    }
  ]
  ```

### Upload Document(s)

Uploads and processes one or multiple files. Ingests content via PyMuPDF, executes semantic chunking, embeds text, indexes vectors into VectorStore and PostgreSQL, synchronizes storage with Cloudflare R2 / local disk, and runs an automated retrieval smoke test before returning status.

- **Method**: `POST`
- **Path**: `/api/documents`
- **Authentication**: Optional (`Authorization: Bearer <TOKEN>` or `x-user-id`)
- **Upload Access Key**: Supported via `x-access-key` header when configured via `UPLOAD_ACCESS_KEY`
- **Content-Type**: `multipart/form-data`
- **Form Parameters**:
  - `file`: A single file or multiple file parts. Supported extensions: `.pdf`, `.txt`, `.md`, `.json`. Maximum file size: 25 MB.
- **Success Response (Single File)** (`200 OK`):
  ```json
  {
    "ok": true,
    "document": {
      "id": "<DOCUMENT_ID>",
      "filename": "<DOCUMENT_ID>.pdf",
      "originalFilename": "Distributed_Locks.pdf",
      "mimeType": "application/pdf",
      "size": 1048576,
      "uploadedAt": "2026-09-17T12:00:00+00:00",
      "lastModified": "2026-09-17T12:00:00+00:00",
      "pageCount": 12,
      "chunkCount": 24,
      "chunkIds": ["<CHUNK_ID_1>", "<CHUNK_ID_2>"],
      "processingStatus": "completed",
      "indexStatus": "indexed",
      "ownerId": "user_<UUID>",
      "owner_id": "user_<UUID>",
      "hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    },
    "results": [
      {
        "ok": true,
        "status": 200,
        "document": { /* DocumentItem */ }
      }
    ]
  }
  ```
- **Success Response (Multi-File)** (`200 OK` or `207 Multi-Status`):
  ```json
  {
    "ok": true,
    "document": { /* first DocumentItem */ },
    "documents": [ /* array of successfully ingested DocumentItems */ ],
    "results": [ /* individual file status objects */ ]
  }
  ```
- **Error Responses**:
  - `400 Bad Request`: No files provided, unsupported file extension, or file is 0 bytes.
  - `401 Unauthorized`: Invalid `x-access-key` header when access control is enabled.
  - `409 Conflict`: Duplicate file detected (SHA-256 hash collision with an existing document belonging to the same owner).
  - `413 Payload Too Large`: Uploaded file exceeds the 25 MB limit.
  - `422 Unprocessable Entity`: Text extraction produced 0 chunks (e.g., scanned PDF without OCR text layer).
  - `500 Internal Server Error`: Storage write error or ingestion retrieval smoke test failure.

### Delete Document

Permanently removes a document, purges its vector embeddings from memory and PostgreSQL, removes binary files from Cloudflare R2 / disk, and updates the catalog.

- **Method**: `DELETE`
- **Path**: `/api/documents/{doc_id}`
- **Authentication**: Optional (evaluated via caller identity)
- **Authorization Rules**:
  - Authenticated document owners may delete their own documents.
  - Administrators may delete any document, including public documents.
  - Non-administrators cannot delete public or system documents.
  - Guests cannot delete documents belonging to registered users.
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "id": "<DOCUMENT_ID>",
    "message": "Document deleted successfully"
  }
  ```
- **Error Responses**:
  - `403 Forbidden`: Caller lacks permission to delete this document, or caller is a non-admin attempting to delete a public document.
  - `404 Not Found`: Document ID not found in database or manifest.
  - `500 Internal Server Error`: Deletion failed and was safely rolled back.

### Stream Document PDF / Raw Content

Streams the raw binary document (PDF or text) for inline viewing in PDF.js or browser tabs. Supports HTTP byte range requests.

- **Method**: `GET`
- **Path**:
  - `/api/documents/{doc_id}/pdf`
  - `/api/documents/{doc_id}/raw` (alias endpoint)
- **Authentication**: Optional (evaluated via caller identity)
- **Authorization Rules**:
  - Public documents are viewable by all callers.
  - Private documents are viewable only by the document owner or an administrator.
  - Guests may view guest-owned documents.
- **Delivery Mechanics**:
  1. **Cloudflare R2**: When configured with S3-compatible credentials, generates a presigned URL (300-second TTL) and returns an `HTTP 307 Temporary Redirect`.
  2. **Storage Service Stream**: If object exists in storage abstraction, streams bytes directly with `Accept-Ranges: bytes` and `Content-Disposition: inline`.
  3. **Local Filesystem Fallback**: Streams file directly from `data/uploads/` with `FileResponse`.
- **Response Headers**:
  - `Content-Disposition: inline; filename="<original_filename>"`
  - `Accept-Ranges: bytes`
  - `Cache-Control: private, max-age=300`
- **Error Responses**:
  - `403 Forbidden`: Caller lacks permission to access the document.
  - `404 Not Found`: Document metadata or binary object not found.

### Reindex Document

Forces text re-extraction, re-chunking, and re-indexing of an existing uploaded file without requiring a re-upload.

- **Method**: `POST`
- **Path**: `/api/documents/{doc_id}/reindex`
- **Authentication**: Required (Document owner or administrator)
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "status": 200,
    "message": "Document 'Operating_Systems_Concepts.pdf' successfully re-indexed.",
    "doc_id": "<DOCUMENT_ID>",
    "chunks_indexed": 85
  }
  ```
- **Error Responses**:
  - `403 Forbidden`: Caller does not own the document and is not an administrator.
  - `404 Not Found`: Document record or underlying file missing.

### Inspect Document Health

Validates document integrity on disk and within the vector store (checks page count, text length, chunk count, and index availability).

- **Method**: `GET`
- **Path**: `/api/documents/{doc_id}/inspect`
- **Authentication**: None
- **Success Response** (`200 OK`):
  ```json
  {
    "valid": true,
    "doc_id": "<DOCUMENT_ID>",
    "filename": "<DOCUMENT_ID>.pdf",
    "page_count": 12,
    "extracted_chars": 28450,
    "chunks_in_file": 24,
    "chunks_in_index": 24
  }
  ```
- **Error Response** (`404 Not Found`):
  ```json
  {
    "valid": false,
    "error": "Document '<DOCUMENT_ID>' not found in manifest."
  }
  ```

---

## 5. Evaluation API

Mounted under `/api/evaluation`.

### Get Evaluation Metrics

Returns live telemetry metrics, latency percentiles per execution mode, and empirical retrieval comparisons.

- **Method**: `GET`
- **Path**: `/api/evaluation`
- **Authentication**: None (Public)
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "latestRequest": {
      "requestId": "req-1789629000000",
      "mode": "adaptive_rag",
      "latencyMs": 1450,
      "ttftMs": 420,
      "totalTokens": 380
    },
    "modePercentiles": {
      "fast": { "sampleCount": 35, "measuredP50LatencyMs": 950.0, "measuredP95LatencyMs": 1400.0, "measuredP50TtftMs": 350.0, "measuredP95TtftMs": 620.0 },
      "adaptive_rag": { "sampleCount": 82, "measuredP50LatencyMs": 1650.0, "measuredP95LatencyMs": 2450.0, "measuredP50TtftMs": 480.0, "measuredP95TtftMs": 850.0 },
      "deep_research": { "sampleCount": 40, "measuredP50LatencyMs": 2850.0, "measuredP95LatencyMs": 3900.0, "measuredP50TtftMs": 610.0, "measuredP95TtftMs": 1100.0 },
      "general_chat": { "sampleCount": 20, "measuredP50LatencyMs": 820.0, "measuredP95LatencyMs": 1200.0, "measuredP50TtftMs": 310.0, "measuredP95TtftMs": 550.0 }
    },
    "retrievalComparison": {
      "lexical_bm25": { "precision_at_k": 0.72, "recall_at_k": 0.68, "mrr": 0.75, "latency_ms": 12.5 },
      "semantic_embedding": { "precision_at_k": 0.84, "recall_at_k": 0.88, "mrr": 0.86, "latency_ms": 110.0 },
      "hybrid_rrf": { "precision_at_k": 0.94, "recall_at_k": 0.96, "mrr": 0.95, "latency_ms": 118.0 }
    },
    "numBenchmarkQueries": 20,
    "corpusInfo": "Data Structures Full Notes.pdf (34 chunks, 8 pages, 6.2 KB vocabulary)",
    "embeddingCache": { "hits": 45, "misses": 15, "hitRatio": 0.75 },
    "bestMeasuredArchitecture": "hybrid_rrf",
    "calibration": {
      "recommended_top_k": 5,
      "recommended_rerank_threshold": 0.65
    },
    "totalQueries": 177,
    "averageLatencyMs": 1650.0,
    "averageTtftMs": 480.0,
    "answerableRatio": 0.94,
    "averageFaithfulness": 96.5,
    "averageCoverage": 0.91
  }
  ```

### Run Evaluation Benchmark

Triggers an on-demand empirical benchmark across the technical query test suite and updates cached measurements.

- **Method**: `POST`
- **Path**: `/api/evaluation/run`
- **Authentication**: None
- **Success Response** (`200 OK`):
  Returns refreshed benchmark comparison object, mode percentiles, and timestamp:
  ```json
  {
    "ok": true,
    "benchmark": { /* benchmark measurements */ },
    "latestRequest": { /* latest telemetry */ },
    "modePercentiles": { /* mode percentiles */ },
    "retrievalComparison": { /* comparative metrics */ },
    "numBenchmarkQueries": 20,
    "corpusInfo": "Data Structures Full Notes.pdf (34 chunks, 8 pages, 6.2 KB vocabulary)",
    "embeddingCache": { /* telemetry */ },
    "bestMeasuredArchitecture": "hybrid_rrf",
    "calibration": { /* calibration values */ },
    "timestamp": "2026-09-17T12:00:00+00:00"
  }
  ```

---

## 6. Health API

CogniFlow mounts health check handlers across three root and sub-path routes:

- `GET /health`
- `GET /api/health`
- `GET /api`

All three routes invoke the identical health status handler.

- **Method**: `GET`
- **Authentication**: None (Public)
- **Success Response** (`200 OK`):
  ```json
  {
    "ok": true,
    "status": "online",
    "engine": "CogniFlow Python FastAPI Adaptive RAG Engine",
    "version": "2.0.0",
    "index_ready": true,
    "indexed_documents": 2,
    "indexed_chunks": 48,
    "index_version": 2,
    "last_index_update": "2026-09-17T10:00:00+00:00",
    "active_provider": "gemini",
    "model": "gemini-2.5-flash"
  }
  ```

---

## 7. Authentication and Headers

### Authorization Bearer Token

- **Header Format**: `Authorization: Bearer <TOKEN>`
- **Token Format**: Standard JSON Web Token (JWT) signed via HS256 using the server-configured `JWT_SECRET`.
- **Payload Schema**:
  - `sub`: User ID (`"user_<UUID>"`)
  - `email`: User email address
  - `name`: User display name
  - `exp`: Expiration timestamp (default: 14 days from issue)
  - `iat`: Issuance timestamp

### Development and Guest Header (`x-user-id`)

- **Header Format**: `x-user-id: <USER_ID>`
- **Purpose**: Allows development testing and guest session isolation without authenticating.
- **Anti-Spoofing Constraints**:
  1. **Dual Header Consistency**: When both `Authorization` and `x-user-id` are present, the value of `x-user-id` **must match** the verified token's `sub` claim. If mismatched, the server aborts with `403 Forbidden`.
  2. **Unauthenticated User Account Protection**: An unauthenticated request **cannot** provide an `x-user-id` starting with `user_` or matching any existing registered user account. Such requests are rejected with `401 Unauthorized`.
  3. **Privilege Protection**: An unauthenticated request **cannot** pass `admin`, `system`, or `root` as `x-user-id`. Such requests are rejected with `401 Unauthorized`.
  4. Values such as `dev-user`, `guest`, or `user_default` resolve safely to the unauthenticated `dev-user` guest workspace.

### Upload Access Key (`x-access-key`)

- **Header Format**: `x-access-key: <KEY>`
- **Purpose**: Optional upload gatekeeper. If the `UPLOAD_ACCESS_KEY` environment variable is defined on the backend, upload requests to `POST /api/documents` must provide this header matching the configured secret.

---

## 8. SSE Event Format

During streaming via `POST /api/chat`, the backend yields Server-Sent Events formatted as:

```
data: {"type": "<EVENT_TYPE>", ...}\n\n
```

An initial SSE comment is transmitted immediately upon connection:
```
: connected\n\n
```

### Confirmed Event Types and Payloads

#### 1. Connection and Request Lifecycle
- `connected`: Sent immediately upon establishing the stream.
  ```json
  { "type": "connected", "requestId": "req-1789629000000", "timestamp": 1789629000000 }
  ```
- `request_started`: Indicates pipeline execution has commenced.
  ```json
  { "type": "request_started", "requestId": "req-1789629000000", "stage": "pipeline", "status": "STARTED", "mode": "adaptive_rag", "provider": "gemini", "model": "gemini-2.5-flash", "timestamp": 1789629000000 }
  ```
- `request_completed`: Signals that the pipeline completed execution.
  ```json
  { "type": "request_completed", "requestId": "req-1789629000000", "latencyMs": 1420 }
  ```
- `cancelled`: Emitted if the client abruptly disconnects before generation begins.
  ```json
  { "type": "cancelled", "reason": "Client disconnected before pipeline start" }
  ```

#### 2. Pipeline Routing and Execution Stages
- `route_selected`: Routing agent decision describing strategy and complexity.
  ```json
  { "type": "route_selected", "requestId": "req-1789629000000", "mode": "adaptive_rag", "complexity": "moderate", "reason": "Technical query requiring hybrid evidence lookup." }
  ```
- `stage_queued` / `stage_started` / `stage_completed` / `stage_skipped`: Lifecycle updates for pipeline stages (`routing`, `retrieval`, `reranking`, `generation`, `verification`).
- `agent_start` / `agent_finish`: Granular start/stop events for individual sub-agents.

#### 3. Retrieval and Reranking
- `retrieval_scope`: Declares whether retrieval is corpus-wide or document-targeted.
  ```json
  { "type": "retrieval_scope", "scope": "DOCUMENT", "documentId": "<DOCUMENT_ID>" }
  ```
- `retrieval_started`: Commences candidate extraction.
  ```json
  { "type": "retrieval_started", "query": "b-tree rebalancing", "mode": "adaptive_rag", "topK": 5 }
  ```
- `retrieval_completed`: Documents retrieved candidate count and retrieval latency.
  ```json
  { "type": "retrieval_completed", "candidatesCount": 8, "latencyMs": 85 }
  ```
- `reranking_started` / `reranking_completed` / `reranking_skipped`: Cross-encoder / Flash-reranker execution status.
- `mmr_applied`: Emitted when Maximal Marginal Relevance diversification is applied.
  ```json
  { "type": "mmr_applied", "count": 5 }
  ```
- `sources`: Dispatches the final list of cited sources before generation begins.
  ```json
  {
    "type": "sources",
    "sources": [
      {
        "chunkId": "<CHUNK_ID>",
        "documentId": "<DOCUMENT_ID>",
        "documentTitle": "Data Structures Notes",
        "authors": "Unknown",
        "year": 0,
        "source": "page_4",
        "chunkIndex": 3,
        "chunkContent": "When a leaf node exceeds capacity...",
        "score": 0.94,
        "pageNumber": 4,
        "section": null
      }
    ]
  }
  ```

#### 4. Generation and Tokens
- `generation_started`: Commences LLM inference.
  ```json
  { "type": "generation_started", "requestId": "req-1789629000000", "provider": "gemini", "model": "gemini-2.5-flash" }
  ```
- `token`: Individual streamed token delta.
  ```json
  { "type": "token", "delta": "When " }
  ```
- `text_delta`: Text delta emitted during generation.
  ```json
  { "type": "text_delta", "delta": "rebalancing " }
  ```
- `generation_completed`: Inference concluded.
  ```json
  { "type": "generation_completed", "tokenCount": 240, "durationMs": 850 }
  ```
- `final_answer_started`: Emitted before the synthesized final answer block streams.
- `summary_started`: Emitted when hierarchical document summarization executes.

#### 5. Citations and Verification
- `citation` / `citation_event`: Emitted when a specific citation bracket (e.g. `[1]`) is resolved to an exact source chunk and page.
  ```json
  {
    "type": "citation",
    "citationIndex": 1,
    "chunkId": "<CHUNK_ID>",
    "documentId": "<DOCUMENT_ID>",
    "documentTitle": "Data Structures Notes",
    "pageNumber": 4,
    "quote": "When a leaf node exceeds capacity..."
  }
  ```
- `verification_started` / `verification_completed` / `verification_skipped`: Critic agent claim-verification status.
- `answerability_result`: Groundedness assessment emitted by the Critic agent.
  ```json
  {
    "type": "answerability_result",
    "status": "fully_answerable",
    "answerable": true,
    "confidence": 0.96,
    "reason": "Direct empirical grounding identified in corpus"
  }
  ```

#### 6. Pipeline Complete
- `pipeline_complete`: Final event delivering the complete result object, sources, execution steps, and duration.
  ```json
  {
    "type": "pipeline_complete",
    "result": {
      "question": "Explain B-Tree rebalancing.",
      "answer": "When a leaf node exceeds capacity...",
      "sources": [ /* CitedSource */ ],
      "steps": [ /* AgentStep */ ],
      "totalDurationMs": 1420,
      "plan": { "queryType": "technical", "searchStrategy": "hybrid" },
      "confidence": { "score": 0.94, "sufficient": true },
      "answerability": { "status": "fully_answerable", "answerable": true }
    }
  }
  ```

---

## 9. Error Handling

### HTTP Status Codes

The API utilizes standard HTTP response status codes:

- `200 OK`: Request succeeded.
- `207 Multi-Status`: Multi-file upload where some files succeeded and others encountered errors.
- `307 Temporary Redirect`: Presigned storage URL redirection for PDF delivery.
- `400 Bad Request`: Missing required fields, invalid JSON syntax, invalid query parameters, or string constraints violated.
- `401 Unauthorized`: Authentication missing, expired, invalid, or access key invalid.
- `403 Forbidden`: Authenticated caller lacks permissions to access, delete, or reindex the target asset, or identity spoofing detected.
- `404 Not Found`: Requested document, conversation, or storage object does not exist.
- `409 Conflict`: Resource collision (duplicate email on registration or duplicate document SHA-256 hash).
- `413 Payload Too Large`: Upload exceeds the 25 MB size limit.
- `422 Unprocessable Entity`: File format is valid, but content contains zero extractable text chunks (e.g., scanned PDF).
- `500 Internal Server Error`: Storage failure, database exception, or failed ingestion rollback.

### Error Response Schemas

#### Standard FastAPI Error Format
Emitted by authentication, conversation, and health endpoints:
```json
{
  "detail": "Conversation not found or access is not authorized."
}
```

#### Structured Error Format
Emitted by document upload, deletion, and reindexing endpoints:
```json
{
  "ok": false,
  "error": {
    "code": "DUPLICATE",
    "message": "File 'Data_Structures.pdf' already exists in your knowledge base."
  }
}
```

---

## 10. Authorization Model

### Authenticated User Isolation

- Every registered user is assigned a permanent `id` in the format `user_<UUID>`.
- Conversations and messages are strictly isolated by `user_id`. Querying or modifying a conversation with an ID owned by another user yields `404 Not Found` to prevent resource probing.
- Uploaded documents inherit the uploader's `user_id` as their `owner_id`.

### Document Ownership and Visibility

- **Private Documents**: Accessible only to the user whose `user_id` matches the document's `owner_id`.
- **Public Documents**: Documents with `owner_id` set to `"public"` or `"system_public"` are queryable and readable by all users and guest workspaces. Public documents cannot be deleted or reindexed by non-admin callers.

### Administrator Privileges

A caller is granted administrative authorization if any of the following conditions are met:
1. The user record contains `role = "admin"`.
2. The user's email address matches one of the pre-configured administrative domains:
   - `admin@cogniflow.local`
   - `admin@cogniflow.test`
   - `admin@demo.cogniflow`
   - `admin@cogniflow.ai`
3. The user ID matches the server environment variable `ADMIN_USER_ID`.

Administrators possess system-wide privileges:
- View all documents across all users and workspaces in `GET /api/documents`.
- Delete any document, including public and system documents.
- Reindex any document in the system.

### Guest / Development Workspace Behavior

- Requests omitting an `Authorization` header execute within the guest workspace (`dev-user`).
- Guests can view public documents and guest documents.
- Guests cannot view or delete documents owned by registered accounts.
- Anti-spoofing logic blocks guests from submitting headers that attempt to impersonate registered users or admins without a valid JWT token.

---

## 11. Example Requests

### 1. Health Check
```bash
curl -s http://localhost:3001/api/health
```

### 2. User Registration
```bash
curl -s -X POST http://localhost:3001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Jane Doe",
    "email": "jane@example.com",
    "password": "strongPassword123"
  }'
```

### 3. User Login
```bash
curl -s -X POST http://localhost:3001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "jane@example.com",
    "password": "strongPassword123"
  }'
```

### 4. List Documents
```bash
curl -s -H "Authorization: Bearer <TOKEN>" \
  http://localhost:3001/api/documents
```

### 5. Upload Document
```bash
curl -s -X POST http://localhost:3001/api/documents \
  -H "Authorization: Bearer <TOKEN>" \
  -F "file=@Sample_Notes.pdf"
```

### 6. Stream Chat Query via SSE
```bash
curl -N -X POST http://localhost:3001/api/chat \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the primary tradeoffs of B-Trees vs LSM Trees?",
    "mode": "adaptive_rag",
    "conversation_id": "<CONVERSATION_ID>"
  }'
```

### 7. Stream PDF Bytes (Range Request)
```bash
curl -s -H "Authorization: Bearer <TOKEN>" \
  -H "Range: bytes=0-4095" \
  http://localhost:3001/api/documents/<DOCUMENT_ID>/pdf \
  -o chunk.pdf
```

### 8. Run Evaluation Benchmark
```bash
curl -s -X POST http://localhost:3001/api/evaluation/run
```

---

## 12. API Notes

### Server-Sent Events (SSE) Proxy Considerations

- Reverse proxies (such as Nginx, Render, Cloudflare, or Vercel edge functions) must not buffer responses from `/api/chat`.
- The endpoint explicitly sets `X-Accel-Buffering: no` and `Cache-Control: no-cache, no-transform`.
- The immediate `: connected\n\n` SSE comment is dispatched to prime intermediate proxies and establish HTTP streaming immediately.
- Client applications should utilize the standard browser `EventSource` or `fetch` with a `ReadableStreamDefaultReader`.

### PDF and Range Streaming

- `/api/documents/{doc_id}/pdf` emits `Accept-Ranges: bytes` to enable standard PDF rendering engines (such as PDF.js) to perform on-demand page streaming without downloading entire large files into browser memory.
- When backed by Cloudflare R2 object storage, the endpoint issues an HTTP `307 Temporary Redirect` to a short-lived presigned URL. Clients must follow HTTP redirects.

### Asynchronous Message Persistence

- In `/api/chat`, user messages are persisted prior to streaming, while the final synthesized response and detailed RAG execution metadata (citations, agent steps, latency) are persisted asynchronously after the stream concludes. This guarantees that database serialization never blocks generative token delivery.

### Query and File Limitations

- **Question Length**: Maximum 1,500 characters. Longer prompts are rejected with `400 Bad Request`.
- **Upload File Size**: Maximum 25 MB per file. Larger payloads are rejected with `413 Payload Too Large`.
- **Supported File Types**: `.pdf`, `.txt`, `.md`, `.json`.
