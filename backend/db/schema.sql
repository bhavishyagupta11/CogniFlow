-- ===========================================================================
-- CogniFlow Unified Database Schema (PostgreSQL & SQLite compatible)
-- Supports users, conversations, messages, documents, chunks, embeddings, summaries
-- ===========================================================================

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 2. Conversations Table
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'deep_research',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated ON conversations(user_id, updated_at DESC);

-- 3. Messages Table
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_conv_created ON messages(conversation_id, created_at ASC);

-- 4. Documents Table (Replaces manifest.json)
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL DEFAULT 'dev-user',
    tenant_id TEXT NOT NULL DEFAULT 'dev-user',
    original_filename TEXT NOT NULL,
    storage_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL DEFAULT 'application/pdf',
    size_bytes INTEGER NOT NULL DEFAULT 0,
    file_hash TEXT NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 1,
    char_count INTEGER NOT NULL DEFAULT 0,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    processing_status TEXT NOT NULL DEFAULT 'completed',
    index_status TEXT NOT NULL DEFAULT 'indexed',
    index_version INTEGER NOT NULL DEFAULT 1,
    r2_upload_key TEXT NOT NULL,
    r2_extracted_key TEXT,
    lifecycle_state TEXT NOT NULL DEFAULT 'ACTIVE', -- ACTIVE | DELETING | DELETED
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_owner ON documents(owner_id);
CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash);
CREATE INDEX IF NOT EXISTS idx_documents_lifecycle ON documents(lifecycle_state);

-- 5. Document Chunks Table (Enables instant in-memory vector rebuild on boot)
CREATE TABLE IF NOT EXISTS document_chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    page_number INTEGER NOT NULL,
    page_start INTEGER NOT NULL DEFAULT 1,
    page_end INTEGER NOT NULL DEFAULT 1,
    section TEXT DEFAULT '',
    subsection TEXT DEFAULT '',
    source_location TEXT DEFAULT '',
    content TEXT NOT NULL,
    char_count INTEGER NOT NULL DEFAULT 0,
    token_count INTEGER NOT NULL DEFAULT 0,
    authors TEXT DEFAULT 'Uploaded Document',
    year INTEGER DEFAULT 2026,
    source TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_idx ON document_chunks(document_id, chunk_index ASC);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_id ON document_chunks(chunk_id);

-- 6. Document Embeddings Table (Persistent neural vectors surviving container restart)
CREATE TABLE IF NOT EXISTS document_embeddings (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'neural_dense',
    model TEXT NOT NULL DEFAULT 'gemini-embedding-001',
    dimensions INTEGER NOT NULL DEFAULT 3072,
    version INTEGER NOT NULL DEFAULT 1,
    embedding_vector_json TEXT NOT NULL, -- JSON-encoded float array
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_embeddings_doc ON document_embeddings(document_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk ON document_embeddings(chunk_id);

-- 7. Document Summaries Table (Persistent hierarchical summaries surviving container restart)
CREATE TABLE IF NOT EXISTS document_summaries (
    id TEXT PRIMARY KEY, -- Hash key of doc_id:doc_hash:page_range:config_hash
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_range TEXT NOT NULL DEFAULT 'all',
    config_hash TEXT NOT NULL DEFAULT 'v1',
    summary_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_summaries_doc ON document_summaries(document_id);

-- 8. Conversation Documents (Explicit chat-scoped sources mapping)
CREATE TABLE IF NOT EXISTS conversation_documents (
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (conversation_id, document_id)
);
CREATE INDEX IF NOT EXISTS idx_conv_docs_conv ON conversation_documents(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conv_docs_doc ON conversation_documents(document_id);
