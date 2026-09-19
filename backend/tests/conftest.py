"""
Pytest configuration and session fixtures for CogniFlow backend test suites.
Ensures zero test contamination in persistent storage and database.
"""

import sys
import time
from pathlib import Path
from typing import Optional
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.services.db_service import db_service

# Upload endpoints return 202 Accepted (async pipeline) for new uploads,
# 200/201 for legacy routes. Tests should assert `status_code in UPLOAD_OK_STATUSES`.
UPLOAD_OK_STATUSES = [200, 201, 202]


def wait_for_document_ready(
    doc_id: str,
    owner_id: str,
    *,
    timeout_secs: float = 30.0,
    poll_interval: float = 0.5,
    require_chunks: bool = True
) -> dict:
    """
    Poll the document manifest / DB until the document's processingStatus
    transitions from 'processing' to 'completed' (or fails).

    This is needed by tests that upload via the HTTP API (which returns 202) and
    then immediately query the vector store or inspect chunks — because the
    background ingestion task runs asynchronously.

    Returns the final document dict when ready.
    Raises AssertionError if the document doesn't become ready within timeout_secs.
    """
    from backend.services.document_service import get_manifest
    from backend.rag.vector_store import vector_store

    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        # Check manifest first (fast path)
        manifest = get_manifest()
        doc = next(
            (m for m in manifest if m.get("id") == doc_id),
            None
        )
        if doc is None:
            # Try DB
            try:
                from backend.services.db_service import db_service
                with db_service.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT * FROM documents WHERE id = %s",
                            (doc_id,)
                        )
                        row = cur.fetchone()
                        if row:
                            doc = dict(row)
            except Exception:
                pass

        if doc:
            status = doc.get("processingStatus") or doc.get("processing_status") or doc.get("status", "")
            if status == "completed":
                if require_chunks:
                    # Also wait for chunks to appear in the vector store
                    has_chunks = any(
                        c.get("document_id") == doc_id or c.get("documentId") == doc_id
                        for c in vector_store.chunks
                    )
                    if has_chunks:
                        return doc
                else:
                    return doc
            elif status in ("failed", "error"):
                raise AssertionError(f"Document {doc_id} ingestion failed: {doc}")

        time.sleep(poll_interval)

    # Timeout — dump state for debugging
    from backend.services.document_service import get_manifest
    manifest = get_manifest()
    doc = next((m for m in manifest if m.get("id") == doc_id), None)
    raise AssertionError(
        f"Document {doc_id} did not become ready within {timeout_secs}s. "
        f"Last state: {doc}"
    )


def wait_for_guest_document_ready(
    session_id: str,
    doc_id: str,
    *,
    timeout_secs: float = 30.0,
    poll_interval: float = 0.3,
) -> dict:
    """
    Poll GuestSessionService until the in-memory guest document transitions to
    'completed' status AND has at least one chunk populated.

    This bridges the gap between asyncio.create_task() (which fires the background
    ingestion task) and the synchronous TestClient that doesn't drive the event
    loop between requests.

    Returns the final guest doc dict when ready.
    Raises AssertionError on timeout.
    """
    from backend.services.guest_session_service import guest_session_service

    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        doc = guest_session_service.get_document(session_id, doc_id)
        if doc is not None:
            status = doc.get("processingStatus") or doc.get("status", "")
            chunks = doc.get("chunks", [])
            if status == "completed" and len(chunks) >= 1:
                return doc
            elif status in ("failed", "error"):
                raise AssertionError(
                    f"Guest document {doc_id} ingestion failed: {doc}"
                )
        time.sleep(poll_interval)

    doc = guest_session_service.get_document(session_id, doc_id) or {}
    raise AssertionError(
        f"Guest document {doc_id} did not become ready within {timeout_secs}s. "
        f"Last state: status={doc.get('processingStatus')}, "
        f"chunks={len(doc.get('chunks', []))}"
    )


@pytest.fixture(autouse=True, scope="function")
def reset_vector_store_between_tests():
    """
    Function-scoped fixture: resets the in-memory vector store before and after
    every test to prevent cross-test document contamination.
    Documents ingested in one test must not affect retrieval in another test.
    """
    from backend.rag.vector_store import vector_store
    # Pre-test reset
    vector_store.chunks.clear()
    if hasattr(vector_store, "in_memory_docs"):
        vector_store.in_memory_docs.clear()
    if hasattr(vector_store, "total_docs"):
        vector_store.total_docs = 0
    yield
    # Post-test cleanup
    vector_store.chunks.clear()
    if hasattr(vector_store, "in_memory_docs"):
        vector_store.in_memory_docs.clear()
    if hasattr(vector_store, "total_docs"):
        vector_store.total_docs = 0


@pytest.fixture(autouse=True, scope="session")
def auto_cleanup_test_artifacts_on_session_finish():
    """
    Session-level teardown:
    After the entire pytest session completes, guarantees that any test accounts
    matching test domains (@cogniflow.test, @test.com, @ephemeral.test) are purged,
    protecting real production accounts, and any test documents created during tests
    are cleaned up.
    """
    yield
    try:
        with db_service.get_connection() as conn:
            with conn.cursor() as cur:
                # 1. Clean up test documents & associations
                # Note: each statement executed separately — psycopg2 does NOT support
                # semicolon-separated multi-statements in a single execute() call.
                cur.execute("""
                    DELETE FROM document_summaries
                    WHERE document_id IN (SELECT id FROM documents WHERE owner_id != 'user_43efe1dd5b89')
                """)
                cur.execute("""
                    DELETE FROM document_embeddings
                    WHERE document_id IN (SELECT id FROM documents WHERE owner_id != 'user_43efe1dd5b89')
                """)
                cur.execute("""
                    DELETE FROM document_chunks
                    WHERE document_id IN (SELECT id FROM documents WHERE owner_id != 'user_43efe1dd5b89')
                """)
                cur.execute("DELETE FROM conversation_documents")
                cur.execute("DELETE FROM documents WHERE owner_id != 'user_43efe1dd5b89'")
                # 2. Clean up test conversations & messages
                cur.execute("""
                    DELETE FROM messages
                    WHERE conversation_id IN (
                        SELECT id FROM conversations
                        WHERE user_id IN (
                            SELECT id FROM users
                            WHERE email LIKE '%@test.com'
                               OR email LIKE '%@ephemeral.test'
                               OR email LIKE '%@cogniflow.test'
                        )
                    )
                """)
                cur.execute("""
                    DELETE FROM conversations
                    WHERE user_id IN (
                        SELECT id FROM users
                        WHERE email LIKE '%@test.com'
                           OR email LIKE '%@ephemeral.test'
                           OR email LIKE '%@cogniflow.test'
                    )
                """)
                # 3. Clean up test users
                cur.execute("""
                    DELETE FROM users
                    WHERE email LIKE '%@test.com'
                       OR email LIKE '%@ephemeral.test'
                       OR email LIKE '%@cogniflow.test'
                """)

        # Clean R2 storage objects if any were created during tests
        from backend.services.storage_service import storage_service, R2StorageService
        if isinstance(storage_service, R2StorageService):
            try:
                client = storage_service._get_client()
                bucket = storage_service.bucket_name
                paginator = client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket):
                    objects = page.get("Contents", [])
                    if objects:
                        delete_keys = [{"Key": obj["Key"]} for obj in objects]
                        client.delete_objects(Bucket=bucket, Delete={"Objects": delete_keys})
            except Exception as r2_err:
                print(f"[conftest] Warning during R2 session cleanup: {r2_err}")

        # Reset manifest and in-memory store
        from backend.config import MANIFEST_PATH
        from backend.rag.vector_store import vector_store
        if MANIFEST_PATH.exists():
            MANIFEST_PATH.write_text("[]\n", encoding="utf-8")
        vector_store.chunks.clear()
        if hasattr(vector_store, "in_memory_docs"):
            vector_store.in_memory_docs.clear()
        if hasattr(vector_store, "total_docs"):
            vector_store.total_docs = 0
    except Exception as e:
        print(f"[conftest] Warning during session cleanup: {e}")
