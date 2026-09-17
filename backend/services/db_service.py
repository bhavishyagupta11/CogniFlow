"""
CogniFlow Unified Database Service & Persistence Abstraction
Supports SQLite (local development & offline testing) and PostgreSQL (Supabase production).
Manages users, conversations, messages, documents, chunks, embeddings, and summaries.
"""

from abc import ABC, abstractmethod
import os
import json
import uuid
import sqlite3
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager

from backend.config import DATA_DIR, DATABASE_URL

logger = logging.getLogger("cogniflow.db_service")

DB_PATH = os.path.join(DATA_DIR, "cogniflow.db")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_doc_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Ensures document dictionary contains both snake_case and camelCase keys for contract parity."""
    d = dict(row)
    doc_id = d.get("id") or d.get("document_id")
    d["id"] = doc_id
    d["document_id"] = doc_id
    
    orig_name = d.get("original_filename") or d.get("originalFilename") or "document.pdf"
    d["original_filename"] = orig_name
    d["originalFilename"] = orig_name

    owner = d.get("owner_id") or d.get("ownerId") or "dev-user"
    d["owner_id"] = owner
    d["ownerId"] = owner
    d["tenant_id"] = d.get("tenant_id") or d.get("tenantId") or owner
    d["tenantId"] = d["tenant_id"]

    page_cnt = d.get("page_count") if d.get("page_count") is not None else d.get("pageCount", 1)
    d["page_count"] = page_cnt
    d["pageCount"] = page_cnt

    chunk_cnt = d.get("chunk_count") if d.get("chunk_count") is not None else d.get("chunkCount", 0)
    d["chunk_count"] = chunk_cnt
    d["chunkCount"] = chunk_cnt

    char_cnt = d.get("char_count") if d.get("char_count") is not None else d.get("charCount", 0)
    d["char_count"] = char_cnt
    d["charCount"] = char_cnt

    proc_status = d.get("processing_status") or d.get("processingStatus") or "completed"
    d["processing_status"] = proc_status
    d["processingStatus"] = proc_status

    idx_status = d.get("index_status") or d.get("indexStatus") or "indexed"
    d["index_status"] = idx_status
    d["indexStatus"] = idx_status

    d["size"] = d.get("size_bytes") if d.get("size_bytes") is not None else d.get("size", 0)
    d["size_bytes"] = d["size"]

    d["uploadedAt"] = d.get("created_at") or d.get("uploadedAt") or utc_now_iso()
    d["lastModified"] = d.get("updated_at") or d.get("lastModified") or d["uploadedAt"]
    d["hash"] = d.get("file_hash") or d.get("hash") or ""
    d["file_hash"] = d["hash"]
    d["filename"] = d.get("storage_filename") or d.get("filename") or f"{doc_id}.pdf"
    d["storage_filename"] = d["filename"]
    d["r2_upload_key"] = d.get("r2_upload_key") or f"uploads/{doc_id}/original"
    d["r2_extracted_key"] = d.get("r2_extracted_key") or f"extracted/{doc_id}/pages.json"

    # Parse chunkIds if present
    if "chunk_ids_json" in d and d["chunk_ids_json"]:
        try:
            d["chunkIds"] = json.loads(d["chunk_ids_json"])
        except Exception:
            d["chunkIds"] = []
    elif "chunkIds" not in d:
        d["chunkIds"] = []

    return d


class BaseDatabaseService(ABC):
    """Abstract Base Class for CogniFlow Relational Database."""

    @abstractmethod
    def init_db(self) -> None:
        pass

    @abstractmethod
    def get_connection(self):
        pass

    # Users
    @abstractmethod
    def create_user(self, email: str, name: str, password_hash: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def update_user_password(self, user_id: str, password_hash: str) -> bool:
        pass

    # Conversations
    @abstractmethod
    def create_conversation(self, user_id: str, title: str, mode: str = "deep_research", conv_id: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_conversation(self, conv_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def update_conversation_title(self, conv_id: str, title: str, user_id: str) -> bool:
        pass

    @abstractmethod
    def delete_conversation(self, conv_id: str, user_id: str) -> bool:
        pass

    # Messages
    @abstractmethod
    def save_message(self, conv_id: str, user_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None, msg_id: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def list_messages(self, conv_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete_messages_by_conversation(self, conv_id: str) -> bool:
        pass

    # Documents
    @abstractmethod
    def create_document(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_document_by_hash(self, file_hash: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_documents(self, caller_id: Optional[str] = None, is_admin: bool = False, is_authenticated: bool = False) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def update_document_status(self, doc_id: str, processing_status: str, index_status: str, error_message: Optional[str] = None) -> bool:
        pass

    @abstractmethod
    def mark_document_deleting(self, doc_id: str) -> bool:
        pass

    @abstractmethod
    def delete_document(self, doc_id: str) -> bool:
        pass

    # Chunks
    @abstractmethod
    def save_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]) -> None:
        pass

    @abstractmethod
    def get_chunks_for_document(self, doc_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_all_chunks(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete_chunks(self, doc_id: str) -> None:
        pass

    # Embeddings
    @abstractmethod
    def save_document_embeddings(self, doc_id: str, chunk_embeddings: Dict[str, List[float]], provider: str = "neural_dense", model: str = "gemini-embedding-001", dimensions: int = 3072, version: int = 1) -> None:
        pass

    @abstractmethod
    def get_document_embeddings(self, doc_id: str) -> Dict[str, List[float]]:
        pass

    @abstractmethod
    def get_all_document_embeddings(self) -> Dict[str, Dict[str, List[float]]]:
        pass

    # Summaries
    @abstractmethod
    def save_summary(self, summary_id: str, doc_id: str, page_range: str, config_hash: str, summary_data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def get_summary(self, summary_id: str) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    def delete_summaries_for_document(self, doc_id: str) -> None:
        pass


# ===========================================================================
# SQLite Implementation (Local Development & Offline Testing)
# ===========================================================================

class SqliteDatabaseService(BaseDatabaseService):
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    @contextmanager
    def get_connection(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=20.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_db(self) -> None:
        schema_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                ddl = f.read()
            with self.get_connection() as conn:
                conn.executescript(ddl)
        else:
            with self.get_connection() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        name TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                        title TEXT NOT NULL,
                        mode TEXT NOT NULL DEFAULT 'deep_research',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS messages (
                        id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                        user_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata_json TEXT DEFAULT '{}',
                        created_at TEXT NOT NULL
                    );
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
                        lifecycle_state TEXT NOT NULL DEFAULT 'ACTIVE',
                        error_message TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
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
                    CREATE TABLE IF NOT EXISTS document_embeddings (
                        id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                        chunk_id TEXT NOT NULL,
                        provider TEXT NOT NULL DEFAULT 'neural_dense',
                        model TEXT NOT NULL DEFAULT 'gemini-embedding-001',
                        dimensions INTEGER NOT NULL DEFAULT 3072,
                        version INTEGER NOT NULL DEFAULT 1,
                        embedding_vector_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS document_summaries (
                        id TEXT PRIMARY KEY,
                        document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                        page_range TEXT NOT NULL DEFAULT 'all',
                        config_hash TEXT NOT NULL DEFAULT 'v1',
                        summary_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );
                """)

    # Users
    def create_user(self, email: str, name: str, password_hash: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        uid = user_id or f"user_{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO users (id, email, name, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (uid, email.strip().lower(), name.strip(), password_hash, now, now)
            )
        return {"id": uid, "email": email.strip().lower(), "name": name.strip(), "created_at": now, "updated_at": now}

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
            return dict(row) if row else None

    def update_user_password(self, user_id: str, password_hash: str) -> bool:
        now = utc_now_iso()
        with self.get_connection() as conn:
            cursor = conn.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?", (password_hash, now, user_id))
            return cursor.rowcount > 0

    # Conversations
    def create_conversation(self, user_id: str, title: str, mode: str = "deep_research", conv_id: Optional[str] = None) -> Dict[str, Any]:
        cid = conv_id or f"conv_{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO conversations (id, user_id, title, mode, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (cid, user_id, title.strip(), mode, now, now)
            )
        return {"id": cid, "user_id": user_id, "title": title.strip(), "mode": mode, "created_at": now, "updated_at": now}

    def get_conversation(self, conv_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            if user_id:
                row = conn.execute("SELECT * FROM conversations WHERE id = ? AND user_id = ?", (conv_id, user_id)).fetchone()
            else:
                row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
            if not row:
                return None
            conv = dict(row)
        conv["messages"] = self.list_messages(conv_id, user_id)
        return conv

    def list_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC", (user_id,)).fetchall()
            return [dict(r) for r in rows]

    def update_conversation_title(self, conv_id: str, title: str, user_id: str) -> bool:
        now = utc_now_iso()
        with self.get_connection() as conn:
            cursor = conn.execute("UPDATE conversations SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?", (title.strip(), now, conv_id, user_id))
            return cursor.rowcount > 0

    def delete_conversation(self, conv_id: str, user_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM conversations WHERE id = ? AND user_id = ?", (conv_id, user_id))
            return cursor.rowcount > 0

    # Messages
    def save_message(self, conv_id: str, user_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None, msg_id: Optional[str] = None) -> Dict[str, Any]:
        mid = msg_id or f"msg_{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        meta_json = json.dumps(metadata or {})
        with self.get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (id, conversation_id, user_id, role, content, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (mid, conv_id, user_id, role, content, meta_json, now)
            )
            conn.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
        msg_dict = {"id": mid, "conversation_id": conv_id, "user_id": user_id, "role": role, "content": content, "metadata": metadata or {}, "created_at": now}
        if isinstance(metadata, dict):
            for k, v in metadata.items():
                if k not in msg_dict:
                    msg_dict[k] = v
        return msg_dict

    def list_messages(self, conv_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            if user_id:
                conv = conn.execute("SELECT id FROM conversations WHERE id = ? AND user_id = ?", (conv_id, user_id)).fetchone()
                if not conv:
                    return []
            rows = conn.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conv_id,)).fetchall()
            result = []
            for r in rows:
                m = dict(r)
                meta = {}
                try:
                    meta = json.loads(m.get("metadata_json") or "{}")
                except Exception:
                    meta = {}
                m["metadata"] = meta
                if isinstance(meta, dict):
                    for k, v in meta.items():
                        if k not in m:
                            m[k] = v
                result.append(m)
            return result

    def delete_messages_by_conversation(self, conv_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            return cursor.rowcount > 0

    # Documents
    def create_document(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        formatted = format_doc_dict(doc_data)
        doc_id = formatted["id"]
        now = utc_now_iso()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO documents (
                    id, owner_id, tenant_id, original_filename, storage_filename,
                    mime_type, size_bytes, file_hash, page_count, char_count,
                    chunk_count, processing_status, index_status, index_version,
                    r2_upload_key, r2_extracted_key, lifecycle_state, error_message,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc_id,
                    formatted["owner_id"],
                    formatted["tenant_id"],
                    formatted["original_filename"],
                    formatted["storage_filename"],
                    formatted.get("mime_type", "application/pdf"),
                    formatted["size_bytes"],
                    formatted["file_hash"],
                    formatted["page_count"],
                    formatted["char_count"],
                    formatted["chunk_count"],
                    formatted["processing_status"],
                    formatted["index_status"],
                    formatted.get("index_version", 1),
                    formatted.get("r2_upload_key") or f"uploads/{doc_id}/original",
                    formatted.get("r2_extracted_key") or f"extracted/{doc_id}/pages.json",
                    formatted.get("lifecycle_state", "ACTIVE"),
                    formatted.get("error_message"),
                    formatted.get("created_at", now),
                    formatted.get("updated_at", now)
                )
            )
        return formatted

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if not row:
                return None
            doc = format_doc_dict(dict(row))
            # Populate chunkIds from chunks table
            chunks = conn.execute("SELECT chunk_id FROM document_chunks WHERE document_id = ? ORDER BY chunk_index ASC", (doc_id,)).fetchall()
            doc["chunkIds"] = [c["chunk_id"] for c in chunks]
            return doc

    def get_document_by_hash(self, file_hash: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            if owner_id:
                row = conn.execute(
                    "SELECT * FROM documents WHERE file_hash = ? AND owner_id = ? AND lifecycle_state = 'ACTIVE'",
                    (file_hash, owner_id)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM documents WHERE file_hash = ? AND lifecycle_state = 'ACTIVE'",
                    (file_hash,)
                ).fetchone()
            if not row:
                return None
            doc = format_doc_dict(dict(row))
            chunks = conn.execute("SELECT chunk_id FROM document_chunks WHERE document_id = ? ORDER BY chunk_index ASC", (doc["id"],)).fetchall()
            doc["chunkIds"] = [c["chunk_id"] for c in chunks]
            return doc

    def list_documents(self, caller_id: Optional[str] = None, is_admin: bool = False, is_authenticated: bool = False) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            # Hide documents marked DELETING or DELETED
            base_query = "SELECT * FROM documents WHERE lifecycle_state = 'ACTIVE'"
            
            if is_admin:
                rows = conn.execute(f"{base_query} ORDER BY created_at DESC").fetchall()
            elif is_authenticated and caller_id:
                rows = conn.execute(
                    f"{base_query} AND (owner_id = ? OR owner_id IN ('system_public', 'public')) ORDER BY created_at DESC",
                    (caller_id,)
                ).fetchall()
            else:
                # Guest or unauthenticated
                rows = conn.execute(
                    f"{base_query} AND (owner_id IN ('dev-user', 'guest', 'user_default', 'system_public', 'public')) ORDER BY created_at DESC"
                ).fetchall()

            result = []
            for r in rows:
                doc = format_doc_dict(dict(r))
                result.append(doc)
            return result

    def update_document_status(self, doc_id: str, processing_status: str, index_status: str, error_message: Optional[str] = None) -> bool:
        now = utc_now_iso()
        with self.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE documents SET processing_status = ?, index_status = ?, error_message = ?, lifecycle_state = 'ACTIVE', updated_at = ? WHERE id = ?",
                (processing_status, index_status, error_message, now, doc_id)
            )
            return cursor.rowcount > 0

    def mark_document_deleting(self, doc_id: str) -> bool:
        now = utc_now_iso()
        with self.get_connection() as conn:
            cursor = conn.execute("UPDATE documents SET lifecycle_state = 'DELETING', updated_at = ? WHERE id = ?", (now, doc_id))
            return cursor.rowcount > 0

    def delete_document(self, doc_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            return cursor.rowcount > 0

    # Chunks
    def save_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]) -> None:
        now = utc_now_iso()
        with self.get_connection() as conn:
            conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))
            for idx, c in enumerate(chunks):
                cid = c.get("chunk_id") or f"{doc_id}_c{c.get('page_number', 1)}_{idx}"
                conn.execute(
                    """
                    INSERT INTO document_chunks (
                        id, document_id, chunk_id, chunk_index, page_number,
                        page_start, page_end, section, subsection, source_location,
                        content, char_count, token_count, authors, year, source, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cid,
                        doc_id,
                        cid,
                        idx,
                        c.get("page_number") or c.get("pageNumber", 1),
                        c.get("page_start", c.get("page_number", 1)),
                        c.get("page_end", c.get("page_number", 1)),
                        c.get("section", ""),
                        c.get("subsection", ""),
                        c.get("source_location", ""),
                        c.get("content", ""),
                        len(c.get("content", "")),
                        c.get("token_count", len(c.get("content", "").split())),
                        c.get("authors", "Uploaded Document"),
                        c.get("year", 2026),
                        c.get("source", ""),
                        now
                    )
                )

    def get_chunks_for_document(self, doc_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM document_chunks WHERE document_id = ? ORDER BY chunk_index ASC", (doc_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_all_chunks(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT c.*, d.owner_id, d.original_filename
                FROM document_chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.lifecycle_state = 'ACTIVE'
                ORDER BY c.document_id, c.chunk_index ASC
                """
            ).fetchall()
            result = []
            for r in rows:
                c = dict(r)
                c["ownerId"] = c.get("owner_id", "dev-user")
                c["originalFilename"] = c.get("original_filename", "")
                c["pageNumber"] = c.get("page_number", 1)
                result.append(c)
            return result

    def delete_chunks(self, doc_id: str) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM document_chunks WHERE document_id = ?", (doc_id,))

    # Embeddings
    def save_document_embeddings(self, doc_id: str, chunk_embeddings: Dict[str, List[float]], provider: str = "neural_dense", model: str = "gemini-embedding-001", dimensions: int = 3072, version: int = 1) -> None:
        now = utc_now_iso()
        with self.get_connection() as conn:
            conn.execute("DELETE FROM document_embeddings WHERE document_id = ?", (doc_id,))
            for chunk_id, vec in chunk_embeddings.items():
                emb_id = f"emb_{chunk_id}"
                vec_json = json.dumps(vec)
                conn.execute(
                    """
                    INSERT INTO document_embeddings (
                        id, document_id, chunk_id, provider, model, dimensions, version, embedding_vector_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (emb_id, doc_id, chunk_id, provider, model, dimensions, version, vec_json, now)
                )

    def get_document_embeddings(self, doc_id: str) -> Dict[str, List[float]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT chunk_id, embedding_vector_json FROM document_embeddings WHERE document_id = ?", (doc_id,)).fetchall()
            result = {}
            for r in rows:
                try:
                    result[r["chunk_id"]] = json.loads(r["embedding_vector_json"])
                except Exception:
                    pass
            return result

    def get_all_document_embeddings(self) -> Dict[str, Dict[str, List[float]]]:
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT e.document_id, e.chunk_id, e.embedding_vector_json
                FROM document_embeddings e
                JOIN documents d ON e.document_id = d.id
                WHERE d.lifecycle_state = 'ACTIVE'
                """
            ).fetchall()
            result: Dict[str, Dict[str, List[float]]] = {}
            for r in rows:
                doc_id = r["document_id"]
                if doc_id not in result:
                    result[doc_id] = {}
                try:
                    result[doc_id][r["chunk_id"]] = json.loads(r["embedding_vector_json"])
                except Exception:
                    pass
            return result

    # Summaries
    def save_summary(self, summary_id: str, doc_id: str, page_range: str, config_hash: str, summary_data: Dict[str, Any]) -> None:
        now = utc_now_iso()
        sum_json = json.dumps(summary_data)
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO document_summaries (id, document_id, page_range, config_hash, summary_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (summary_id, doc_id, page_range, config_hash, sum_json, now)
            )

    def get_summary(self, summary_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT summary_json FROM document_summaries WHERE id = ?", (summary_id,)).fetchone()
            if row:
                try:
                    return json.loads(row["summary_json"])
                except Exception:
                    return None
            return None

    def delete_summaries_for_document(self, doc_id: str) -> None:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM document_summaries WHERE document_id = ?", (doc_id,))


# ===========================================================================
# PostgreSQL Implementation (Supabase Cloud Production)
# ===========================================================================

class PostgresConnectionWrapper:
    """Lightweight wrapper ensuring parity between sqlite3 and psycopg2 connection interfaces."""
    def __init__(self, conn):
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def cursor(self, *args, **kwargs):
        if "cursor_factory" not in kwargs:
            import psycopg2.extras
            kwargs["cursor_factory"] = psycopg2.extras.DictCursor
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def execute(self, sql, params=None):
        import psycopg2.extras
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        if params:
            cur.execute(sql.replace("?", "%s"), params)
        else:
            cur.execute(sql)
        return cur


class PostgresDatabaseService(BaseDatabaseService):
    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool = None

    def _get_pool(self):
        if self._pool is None:
            import psycopg2.pool
            clean_url = self.database_url
            if clean_url.startswith("postgres://"):
                clean_url = "postgresql://" + clean_url[len("postgres://"):]
            self._pool = psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=clean_url)
        return self._pool

    @contextmanager
    def get_connection(self):
        pool = self._get_pool()
        raw_conn = pool.getconn()
        wrapped_conn = PostgresConnectionWrapper(raw_conn)
        try:
            yield wrapped_conn
            raw_conn.commit()
        except Exception:
            raw_conn.rollback()
            raise
        finally:
            pool.putconn(raw_conn)

    def init_db(self) -> None:
        schema_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r", encoding="utf-8") as f:
                ddl = f.read()
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(ddl)

    # Users
    def create_user(self, email: str, name: str, password_hash: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        uid = user_id or f"user_{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (id, email, name, password_hash, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (uid, email.strip().lower(), name.strip(), password_hash, now, now)
                )
        return {"id": uid, "email": email.strip().lower(), "name": name.strip(), "created_at": now, "updated_at": now}

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, email, name, password_hash, created_at, updated_at FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if row:
                    cols = [desc[0] for desc in cur.description]
                    return dict(zip(cols, row))
                return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, email, name, password_hash, created_at, updated_at FROM users WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
                row = cur.fetchone()
                if row:
                    cols = [desc[0] for desc in cur.description]
                    return dict(zip(cols, row))
                return None

    def update_user_password(self, user_id: str, password_hash: str) -> bool:
        now = utc_now_iso()
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET password_hash = %s, updated_at = %s WHERE id = %s", (password_hash, now, user_id))
                return cur.rowcount > 0

    # Conversations
    def create_conversation(self, user_id: str, title: str, mode: str = "deep_research", conv_id: Optional[str] = None) -> Dict[str, Any]:
        cid = conv_id or f"conv_{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO conversations (id, user_id, title, mode, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (cid, user_id, title.strip(), mode, now, now)
                )
        return {"id": cid, "user_id": user_id, "title": title.strip(), "mode": mode, "created_at": now, "updated_at": now}

    def get_conversation(self, conv_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute("SELECT id, user_id, title, mode, created_at, updated_at FROM conversations WHERE id = %s AND user_id = %s", (conv_id, user_id))
                else:
                    cur.execute("SELECT id, user_id, title, mode, created_at, updated_at FROM conversations WHERE id = %s", (conv_id,))
                row = cur.fetchone()
                if not row:
                    return None
                cols = [desc[0] for desc in cur.description]
                conv = dict(zip(cols, row))
        conv["messages"] = self.list_messages(conv_id, user_id)
        return conv

    def list_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, user_id, title, mode, created_at, updated_at FROM conversations WHERE user_id = %s ORDER BY updated_at DESC", (user_id,))
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, r)) for r in rows]

    def update_conversation_title(self, conv_id: str, title: str, user_id: str) -> bool:
        now = utc_now_iso()
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE conversations SET title = %s, updated_at = %s WHERE id = %s AND user_id = %s", (title.strip(), now, conv_id, user_id))
                return cur.rowcount > 0

    def delete_conversation(self, conv_id: str, user_id: str) -> bool:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM conversations WHERE id = %s AND user_id = %s", (conv_id, user_id))
                return cur.rowcount > 0

    # Messages
    def save_message(self, conv_id: str, user_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None, msg_id: Optional[str] = None) -> Dict[str, Any]:
        mid = msg_id or f"msg_{uuid.uuid4().hex[:12]}"
        now = utc_now_iso()
        meta_json = json.dumps(metadata or {})
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO messages (id, conversation_id, user_id, role, content, metadata_json, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (mid, conv_id, user_id, role, content, meta_json, now)
                )
                cur.execute("UPDATE conversations SET updated_at = %s WHERE id = %s", (now, conv_id))
        msg_dict = {"id": mid, "conversation_id": conv_id, "user_id": user_id, "role": role, "content": content, "metadata": metadata or {}, "created_at": now}
        if isinstance(metadata, dict):
            for k, v in metadata.items():
                if k not in msg_dict:
                    msg_dict[k] = v
        return msg_dict

    def list_messages(self, conv_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if user_id:
                    cur.execute("SELECT id FROM conversations WHERE id = %s AND user_id = %s", (conv_id, user_id))
                    if not cur.fetchone():
                        return []
                cur.execute("SELECT id, conversation_id, user_id, role, content, metadata_json, created_at FROM messages WHERE conversation_id = %s ORDER BY created_at ASC", (conv_id,))
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                result = []
                for r in rows:
                    m = dict(zip(cols, r))
                    meta = {}
                    try:
                        meta = json.loads(m.get("metadata_json") or "{}")
                    except Exception:
                        meta = {}
                    m["metadata"] = meta
                    if isinstance(meta, dict):
                        for k, v in meta.items():
                            if k not in m:
                                m[k] = v
                    result.append(m)
                return result

    def delete_messages_by_conversation(self, conv_id: str) -> bool:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM messages WHERE conversation_id = %s", (conv_id,))
                return cur.rowcount > 0

    # Documents
    def create_document(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        formatted = format_doc_dict(doc_data)
        doc_id = formatted["id"]
        now = utc_now_iso()
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO documents (
                        id, owner_id, tenant_id, original_filename, storage_filename,
                        mime_type, size_bytes, file_hash, page_count, char_count,
                        chunk_count, processing_status, index_status, index_version,
                        r2_upload_key, r2_extracted_key, lifecycle_state, error_message,
                        created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        owner_id = EXCLUDED.owner_id,
                        original_filename = EXCLUDED.original_filename,
                        storage_filename = EXCLUDED.storage_filename,
                        size_bytes = EXCLUDED.size_bytes,
                        file_hash = EXCLUDED.file_hash,
                        page_count = EXCLUDED.page_count,
                        char_count = EXCLUDED.char_count,
                        chunk_count = EXCLUDED.chunk_count,
                        processing_status = EXCLUDED.processing_status,
                        index_status = EXCLUDED.index_status,
                        lifecycle_state = EXCLUDED.lifecycle_state,
                        error_message = EXCLUDED.error_message,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        doc_id,
                        formatted["owner_id"],
                        formatted["tenant_id"],
                        formatted["original_filename"],
                        formatted["storage_filename"],
                        formatted.get("mime_type", "application/pdf"),
                        formatted["size_bytes"],
                        formatted["file_hash"],
                        formatted["page_count"],
                        formatted["char_count"],
                        formatted["chunk_count"],
                        formatted["processing_status"],
                        formatted["index_status"],
                        formatted.get("index_version", 1),
                        formatted.get("r2_upload_key") or f"uploads/{doc_id}/original",
                        formatted.get("r2_extracted_key") or f"extracted/{doc_id}/pages.json",
                        formatted.get("lifecycle_state", "ACTIVE"),
                        formatted.get("error_message"),
                        formatted.get("created_at", now),
                        formatted.get("updated_at", now)
                    )
                )
        return formatted

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))
                row = cur.fetchone()
                if not row:
                    return None
                cols = [desc[0] for desc in cur.description]
                doc = format_doc_dict(dict(zip(cols, row)))
                cur.execute("SELECT chunk_id FROM document_chunks WHERE document_id = %s ORDER BY chunk_index ASC", (doc_id,))
                doc["chunkIds"] = [r[0] for r in cur.fetchall()]
                return doc

    def get_document_by_hash(self, file_hash: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                if owner_id:
                    cur.execute(
                        "SELECT * FROM documents WHERE file_hash = %s AND owner_id = %s AND lifecycle_state = 'ACTIVE'",
                        (file_hash, owner_id)
                    )
                else:
                    cur.execute(
                        "SELECT * FROM documents WHERE file_hash = %s AND lifecycle_state = 'ACTIVE'",
                        (file_hash,)
                    )
                row = cur.fetchone()
                if not row:
                    return None
                cols = [desc[0] for desc in cur.description]
                doc = format_doc_dict(dict(zip(cols, row)))
                cur.execute("SELECT chunk_id FROM document_chunks WHERE document_id = %s ORDER BY chunk_index ASC", (doc["id"],))
                doc["chunkIds"] = [r[0] for r in cur.fetchall()]
                return doc

    def list_documents(self, caller_id: Optional[str] = None, is_admin: bool = False, is_authenticated: bool = False) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                base_query = "SELECT * FROM documents WHERE lifecycle_state = 'ACTIVE'"
                if is_admin:
                    cur.execute(f"{base_query} ORDER BY created_at DESC")
                elif is_authenticated and caller_id:
                    cur.execute(f"{base_query} AND (owner_id = %s OR owner_id IN ('system_public', 'public')) ORDER BY created_at DESC", (caller_id,))
                else:
                    cur.execute(f"{base_query} AND (owner_id IN ('dev-user', 'guest', 'user_default', 'system_public', 'public')) ORDER BY created_at DESC")
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                return [format_doc_dict(dict(zip(cols, r))) for r in rows]

    def update_document_status(self, doc_id: str, processing_status: str, index_status: str, error_message: Optional[str] = None) -> bool:
        now = utc_now_iso()
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET processing_status = %s, index_status = %s, error_message = %s, lifecycle_state = 'ACTIVE', updated_at = %s WHERE id = %s",
                    (processing_status, index_status, error_message, now, doc_id)
                )
                return cur.rowcount > 0

    def mark_document_deleting(self, doc_id: str) -> bool:
        now = utc_now_iso()
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE documents SET lifecycle_state = 'DELETING', updated_at = %s WHERE id = %s", (now, doc_id))
                return cur.rowcount > 0

    def delete_document(self, doc_id: str) -> bool:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
                return cur.rowcount > 0

    # Chunks
    def save_chunks(self, doc_id: str, chunks: List[Dict[str, Any]]) -> None:
        now = utc_now_iso()
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM document_chunks WHERE document_id = %s", (doc_id,))
                for idx, c in enumerate(chunks):
                    cid = c.get("chunk_id") or f"{doc_id}_c{c.get('page_number', 1)}_{idx}"
                    cur.execute(
                        """
                        INSERT INTO document_chunks (
                            id, document_id, chunk_id, chunk_index, page_number,
                            page_start, page_end, section, subsection, source_location,
                            content, char_count, token_count, authors, year, source, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            cid,
                            doc_id,
                            cid,
                            idx,
                            c.get("page_number") or c.get("pageNumber", 1),
                            c.get("page_start", c.get("page_number", 1)),
                            c.get("page_end", c.get("page_number", 1)),
                            c.get("section", ""),
                            c.get("subsection", ""),
                            c.get("source_location", ""),
                            c.get("content", ""),
                            len(c.get("content", "")),
                            c.get("token_count", len(c.get("content", "").split())),
                            c.get("authors", "Uploaded Document"),
                            c.get("year", 2026),
                            c.get("source", ""),
                            now
                        )
                    )

    def get_chunks_for_document(self, doc_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM document_chunks WHERE document_id = %s ORDER BY chunk_index ASC", (doc_id,))
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, r)) for r in rows]

    def get_all_chunks(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.*, d.owner_id, d.original_filename
                    FROM document_chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE d.lifecycle_state = 'ACTIVE'
                    ORDER BY c.document_id, c.chunk_index ASC
                    """
                )
                rows = cur.fetchall()
                cols = [desc[0] for desc in cur.description]
                result = []
                for r in rows:
                    c = dict(zip(cols, r))
                    c["ownerId"] = c.get("owner_id", "dev-user")
                    c["originalFilename"] = c.get("original_filename", "")
                    c["pageNumber"] = c.get("page_number", 1)
                    result.append(c)
                return result

    def delete_chunks(self, doc_id: str) -> None:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM document_chunks WHERE document_id = %s", (doc_id,))

    # Embeddings
    def save_document_embeddings(self, doc_id: str, chunk_embeddings: Dict[str, List[float]], provider: str = "neural_dense", model: str = "gemini-embedding-001", dimensions: int = 3072, version: int = 1) -> None:
        now = utc_now_iso()
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM document_embeddings WHERE document_id = %s", (doc_id,))
                for chunk_id, vec in chunk_embeddings.items():
                    emb_id = f"emb_{chunk_id}"
                    vec_json = json.dumps(vec)
                    cur.execute(
                        """
                        INSERT INTO document_embeddings (
                            id, document_id, chunk_id, provider, model, dimensions, version, embedding_vector_json, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (emb_id, doc_id, chunk_id, provider, model, dimensions, version, vec_json, now)
                    )

    def get_document_embeddings(self, doc_id: str) -> Dict[str, List[float]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT chunk_id, embedding_vector_json FROM document_embeddings WHERE document_id = %s", (doc_id,))
                result = {}
                for row in cur.fetchall():
                    try:
                        result[row[0]] = json.loads(row[1])
                    except Exception:
                        pass
                return result

    def get_all_document_embeddings(self) -> Dict[str, Dict[str, List[float]]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT e.document_id, e.chunk_id, e.embedding_vector_json
                    FROM document_embeddings e
                    JOIN documents d ON e.document_id = d.id
                    WHERE d.lifecycle_state = 'ACTIVE'
                    """
                )
                result: Dict[str, Dict[str, List[float]]] = {}
                for row in cur.fetchall():
                    doc_id = row[0]
                    if doc_id not in result:
                        result[doc_id] = {}
                    try:
                        result[doc_id][row[1]] = json.loads(row[2])
                    except Exception:
                        pass
                return result

    # Summaries
    def save_summary(self, summary_id: str, doc_id: str, page_range: str, config_hash: str, summary_data: Dict[str, Any]) -> None:
        now = utc_now_iso()
        sum_json = json.dumps(summary_data)
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO document_summaries (id, document_id, page_range, config_hash, summary_json, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET summary_json = EXCLUDED.summary_json, created_at = EXCLUDED.created_at
                    """,
                    (summary_id, doc_id, page_range, config_hash, sum_json, now)
                )

    def get_summary(self, summary_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT summary_json FROM document_summaries WHERE id = %s", (summary_id,))
                row = cur.fetchone()
                if row:
                    try:
                        return json.loads(row[0])
                    except Exception:
                        return None
                return None

    def delete_summaries_for_document(self, doc_id: str) -> None:
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM document_summaries WHERE document_id = %s", (doc_id,))


# ===========================================================================
# Database Factory & Module-Level Interface
# ===========================================================================

def create_database_service() -> BaseDatabaseService:
    clean_url = (DATABASE_URL or "").strip()
    if clean_url.startswith("postgresql://") or clean_url.startswith("postgres://"):
        try:
            logger.info("[Database] Initializing PostgresDatabaseService (Supabase)...")
            return PostgresDatabaseService(clean_url)
        except Exception as e:
            logger.error(f"[Database] Failed to connect to PostgreSQL ({e}), falling back to SqliteDatabaseService.")
            return SqliteDatabaseService()
    return SqliteDatabaseService()


# Active singleton database service
db_service = create_database_service()


# Module-level convenience functions preserving existing API contract
def get_db_connection():
    return db_service.get_connection()

def init_db():
    return db_service.init_db()

def create_user(email: str, name: str, password_hash: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    return db_service.create_user(email, name, password_hash, user_id)

def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    return db_service.get_user_by_id(user_id)

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    return db_service.get_user_by_email(email)

def update_user_password(user_id: str, password_hash: str) -> bool:
    return db_service.update_user_password(user_id, password_hash)

def create_conversation(user_id: str, title: str, mode: str = "deep_research", conv_id: Optional[str] = None) -> Dict[str, Any]:
    return db_service.create_conversation(user_id, title, mode, conv_id)

def get_conversation(conv_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return db_service.get_conversation(conv_id, user_id)

def list_conversations(user_id: str) -> List[Dict[str, Any]]:
    return db_service.list_conversations(user_id)

get_conversations_by_user = list_conversations

def update_conversation_title(conv_id: str, title: str, user_id: str) -> bool:
    return db_service.update_conversation_title(conv_id, title, user_id)

def delete_conversation(conv_id: str, user_id: str) -> bool:
    return db_service.delete_conversation(conv_id, user_id)

def save_message(conv_id: str, user_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None, msg_id: Optional[str] = None) -> Dict[str, Any]:
    return db_service.save_message(conv_id, user_id, role, content, metadata, msg_id)

def list_messages(conv_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
    return db_service.list_messages(conv_id, user_id)

def delete_messages_by_conversation(conv_id: str) -> bool:
    return db_service.delete_messages_by_conversation(conv_id)

# Document & Chunks repository exports
def create_document(doc_data: Dict[str, Any]) -> Dict[str, Any]:
    return db_service.create_document(doc_data)

def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    return db_service.get_document(doc_id)

def get_document_by_hash(file_hash: str, owner_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    return db_service.get_document_by_hash(file_hash, owner_id)

def list_documents(caller_id: Optional[str] = None, is_admin: bool = False, is_authenticated: bool = False) -> List[Dict[str, Any]]:
    return db_service.list_documents(caller_id, is_admin, is_authenticated)

def update_document_status(doc_id: str, processing_status: str, index_status: str, error_message: Optional[str] = None) -> bool:
    return db_service.update_document_status(doc_id, processing_status, index_status, error_message)

def mark_document_deleting(doc_id: str) -> bool:
    return db_service.mark_document_deleting(doc_id)

def delete_document_row(doc_id: str) -> bool:
    return db_service.delete_document(doc_id)

def save_chunks(doc_id: str, chunks: List[Dict[str, Any]]) -> None:
    return db_service.save_chunks(doc_id, chunks)

def get_chunks_for_document(doc_id: str) -> List[Dict[str, Any]]:
    return db_service.get_chunks_for_document(doc_id)

def get_all_chunks() -> List[Dict[str, Any]]:
    return db_service.get_all_chunks()

def delete_chunks(doc_id: str) -> None:
    return db_service.delete_chunks(doc_id)

def save_document_embeddings(doc_id: str, chunk_embeddings: Dict[str, List[float]], provider: str = "neural_dense", model: str = "gemini-embedding-001", dimensions: int = 3072, version: int = 1) -> None:
    return db_service.save_document_embeddings(doc_id, chunk_embeddings, provider, model, dimensions, version)

def get_document_embeddings(doc_id: str) -> Dict[str, List[float]]:
    return db_service.get_document_embeddings(doc_id)

def get_all_document_embeddings() -> Dict[str, Dict[str, List[float]]]:
    return db_service.get_all_document_embeddings()

def save_summary(summary_id: str, doc_id: str, page_range: str, config_hash: str, summary_data: Dict[str, Any]) -> None:
    return db_service.save_summary(summary_id, doc_id, page_range, config_hash, summary_data)

def get_summary(summary_id: str) -> Optional[Dict[str, Any]]:
    return db_service.get_summary(summary_id)

def delete_summaries_for_document(doc_id: str) -> None:
    return db_service.delete_summaries_for_document(doc_id)
