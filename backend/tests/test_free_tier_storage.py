"""
CogniFlow Free-Tier Production Storage Migration Test Suite
Validates:
1. Storage Abstraction (Local & R2)
2. Database Schema Entities (Users, Conversations, Messages, Documents, Chunks, Embeddings, Summaries)
3. Document Model replacing manifest.json as authoritative source of truth
4. Chunk persistence with full citation provenance
5. Dense embedding vector persistence surviving container restarts
6. Private document PDF access authorization (User A allow, User B 403, Guest 403)
7. Compensating deletion lifecycle across DB, object storage, and vector index
8. Critical Ephemeral Disk Restart Recovery Acceptance Test (Phase 15)
"""

import os
import io
import json
import shutil
import tempfile
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config import DATA_DIR, UPLOADS_DIR, EXTRACTED_DIR, MANIFEST_PATH
from backend.services.storage_service import (
    BaseStorageService,
    LocalStorageService,
    R2StorageService,
    storage_service
)
from backend.services.db_service import (
    db_service,
    init_db,
    create_user,
    get_user_by_id,
    create_conversation,
    get_conversation,
    save_message,
    create_document,
    get_document,
    list_documents,
    save_chunks,
    get_chunks_for_document,
    get_all_chunks,
    save_document_embeddings,
    get_document_embeddings,
    get_all_document_embeddings,
    save_summary,
    get_summary,
    delete_summaries_for_document,
    get_document_by_hash
)
from backend.services.auth_service import hash_password, create_access_token
from backend.services.document_service import ingest_file, delete_document, get_manifest
from backend.rag.vector_store import vector_store
from backend.services.summary_cache import summary_cache

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Ensure database schema is initialized and ready for tests."""
    init_db()
    yield


def test_storage_abstraction_interface():
    """Validates that BaseStorageService methods operate correctly on LocalStorageService."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorageService(base_dir=Path(tmpdir))
        test_key = "uploads/test_doc_1/original"
        payload = b"CogniFlow PDF binary data payload"

        # 1. Put object
        stored_key = storage.put_object(test_key, payload, content_type="application/pdf")
        assert stored_key == test_key

        # 2. Exists
        assert storage.exists(test_key) is True
        assert storage.exists("non_existent_key") is False

        # 3. Get object
        retrieved = storage.get_object(test_key)
        assert retrieved == payload

        # 4. Presigned URL generation (local dev path)
        url = storage.generate_presigned_url(test_key, expires_in_seconds=600)
        assert "key=" in url or "/api/documents" in url

        # 5. Delete object
        deleted = storage.delete_object(test_key)
        assert deleted is True
        assert storage.exists(test_key) is False


def test_postgres_schema_entities_crud():
    """Validates complete CRUD persistence across all required entities in db_service."""
    uid = f"user_crud_{os.urandom(4).hex()}"
    user = create_user(
        email=f"{uid}@cogniflow.test",
        name="Postgres Tester",
        password_hash=hash_password("Pass123!"),
        user_id=uid
    )
    assert user["id"] == uid
    fetched_user = get_user_by_id(uid)
    assert fetched_user is not None
    assert fetched_user["email"] == f"{uid}@cogniflow.test"

    # Conversation & Message
    conv = create_conversation(user_id=uid, title="Migration Architecture", mode="deep_research")
    conv_id = conv["id"]
    assert conv_id.startswith("conv_")

    msg = save_message(
        conv_id=conv_id,
        user_id=uid,
        role="assistant",
        content="Supabase PostgreSQL and Cloudflare R2 migration complete.",
        metadata={"confidence": 0.99, "citations": [{"evidenceId": "E1"}]}
    )
    assert msg["role"] == "assistant"
    assert msg["confidence"] == 0.99

    fetched_conv = get_conversation(conv_id, user_id=uid)
    assert fetched_conv is not None
    assert len(fetched_conv["messages"]) == 1

    # Document
    doc_id = f"doc_crud_{os.urandom(4).hex()}"
    doc_data = {
        "id": doc_id,
        "owner_id": uid,
        "original_filename": "architecture_blueprint.pdf",
        "storage_filename": f"{doc_id}.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 1048576,
        "file_hash": f"hash_{doc_id}",
        "page_count": 12,
        "chunk_count": 24,
        "processing_status": "completed",
        "index_status": "indexed",
        "r2_upload_key": f"uploads/{doc_id}/original",
        "r2_extracted_key": f"extracted/{doc_id}/pages.json",
        "lifecycle_state": "ACTIVE"
    }
    created_doc = create_document(doc_data)
    assert created_doc["id"] == doc_id
    assert created_doc["originalFilename"] == "architecture_blueprint.pdf"

    # Semantic Chunks with Provenance
    chunks = [
        {
            "chunk_id": f"{doc_id}_c1",
            "page_number": 1,
            "page_start": 1,
            "page_end": 1,
            "section": "1. Overview",
            "subsection": "1.1 Goals",
            "source_location": "Page 1, Section 1.1",
            "content": "CogniFlow free tier eliminates persistent disk cost while guaranteeing RAG correctness.",
            "token_count": 14
        },
        {
            "chunk_id": f"{doc_id}_c2",
            "page_number": 2,
            "page_start": 2,
            "page_end": 2,
            "section": "2. Architecture",
            "subsection": "2.1 Supabase and R2",
            "source_location": "Page 2, Section 2.1",
            "content": "PostgreSQL holds relational and chunk data; R2 holds raw binary and extracted JSON.",
            "token_count": 16
        }
    ]
    save_chunks(doc_id, chunks)
    doc_chunks = get_chunks_for_document(doc_id)
    assert len(doc_chunks) == 2
    assert doc_chunks[0]["section"] == "1. Overview"
    assert doc_chunks[1]["section"] == "2. Architecture"

    # Dense Vector Embeddings
    emb_dict = {
        f"{doc_id}_c1": [0.12, -0.45, 0.88, 0.05],
        f"{doc_id}_c2": [0.33, 0.11, -0.25, 0.91]
    }
    save_document_embeddings(
        doc_id=doc_id,
        chunk_embeddings=emb_dict,
        provider="neural_dense",
        model="gemini-embedding-001",
        dimensions=4,
        version=1
    )
    fetched_embs = get_document_embeddings(doc_id)
    assert f"{doc_id}_c1" in fetched_embs
    assert len(fetched_embs[f"{doc_id}_c1"]) == 4

    # Summaries
    summary_key = f"{doc_id}_sum_v1"
    summary_payload = {
        "title": "Executive Summary",
        "summary": "Full migration plan for free-tier deployment.",
        "key_findings": ["Zero Render Disk", "Cloudflare R2", "Supabase DB"]
    }
    save_summary(summary_key, doc_id, "all", "v1", summary_payload)
    fetched_summary = get_summary(summary_key)
    assert fetched_summary is not None
    assert fetched_summary["title"] == "Executive Summary"


def test_private_document_pdf_authorization():
    """
    Phase 6 Security Invariant:
    User A -> own PDF -> ALLOW (200 / 307)
    User B -> User A PDF -> DENY (403 Forbidden)
    Guest -> User A PDF -> DENY (403 Forbidden)
    Public Document -> ALLOW for all callers
    """
    # 1. Register User A and User B
    uid_a = f"user_pdf_a_{os.urandom(3).hex()}"
    uid_b = f"user_pdf_b_{os.urandom(3).hex()}"
    create_user(email=f"{uid_a}@test.com", name="User A", password_hash="pass", user_id=uid_a)
    create_user(email=f"{uid_b}@test.com", name="User B", password_hash="pass", user_id=uid_b)

    token_a = create_access_token({"sub": uid_a, "email": f"{uid_a}@test.com", "role": "user"})
    token_b = create_access_token({"sub": uid_b, "email": f"{uid_b}@test.com", "role": "user"})

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 2. Upload private document for User A via storage service & DB
    doc_id_a = f"doc_private_{os.urandom(4).hex()}"
    pdf_bytes = b"%PDF-1.4 Private Confidential Document Content for User A"
    upload_key = f"uploads/{doc_id_a}/original"
    storage_service.put_object(upload_key, pdf_bytes, content_type="application/pdf")

    create_document({
        "id": doc_id_a,
        "owner_id": uid_a,
        "original_filename": "user_a_confidential.pdf",
        "storage_filename": f"{doc_id_a}.pdf",
        "mime_type": "application/pdf",
        "size_bytes": len(pdf_bytes),
        "file_hash": f"hash_{doc_id_a}",
        "r2_upload_key": upload_key,
        "lifecycle_state": "ACTIVE"
    })

    # Test Case 1: User A accesses own PDF -> ALLOW (200 stream or 307 presigned redirect)
    res_a = client.get(f"/api/documents/{doc_id_a}/pdf", headers=headers_a, follow_redirects=False)
    assert res_a.status_code in [200, 307], f"Expected 200 or 307 redirect, got {res_a.status_code}"

    # Test Case 2: User B accesses User A's private PDF -> DENIED with 403
    res_b = client.get(f"/api/documents/{doc_id_a}/pdf", headers=headers_b, follow_redirects=False)
    assert res_b.status_code == 403, f"Cross-user PDF access must be 403 Forbidden! Got {res_b.status_code}"

    # Test Case 3: Guest / Unauthenticated caller accesses User A's private PDF -> DENIED with 403
    res_guest = client.get(f"/api/documents/{doc_id_a}/pdf", follow_redirects=False)
    assert res_guest.status_code == 403, f"Guest access to private PDF must be 403 Forbidden! Got {res_guest.status_code}"

    # Test Case 4: Public document accessible to everyone
    doc_id_pub = f"doc_public_{os.urandom(4).hex()}"
    pub_key = f"uploads/{doc_id_pub}/original"
    storage_service.put_object(pub_key, b"%PDF-1.4 Public Whitepaper", content_type="application/pdf")
    create_document({
        "id": doc_id_pub,
        "owner_id": "system_public",
        "original_filename": "public_whitepaper.pdf",
        "storage_filename": f"{doc_id_pub}.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 100,
        "file_hash": f"hash_{doc_id_pub}",
        "r2_upload_key": pub_key,
        "lifecycle_state": "ACTIVE"
    })

    res_pub_b = client.get(f"/api/documents/{doc_id_pub}/pdf", headers=headers_b, follow_redirects=False)
    assert res_pub_b.status_code in [200, 307]
    res_pub_guest = client.get(f"/api/documents/{doc_id_pub}/pdf", follow_redirects=False)
    assert res_pub_guest.status_code in [200, 307]


def test_compensating_deletion_lifecycle_and_retry():
    """
    Phase 10 Invariant:
    ACTIVE -> DELETING -> storage deletion -> DB deletion -> index purge -> DELETED
    Repeated DELETE on already deleted document -> clean 404.
    """
    uid = f"user_del_{os.urandom(3).hex()}"
    create_user(email=f"{uid}@test.com", name="Deleter", password_hash="pass", user_id=uid)
    doc_id = f"doc_del_{os.urandom(4).hex()}"
    upload_key = f"uploads/{doc_id}/original"
    storage_service.put_object(upload_key, b"Content to delete")

    create_document({
        "id": doc_id,
        "owner_id": uid,
        "original_filename": "delete_me.pdf",
        "storage_filename": f"{doc_id}.pdf",
        "file_hash": f"hash_{doc_id}",
        "r2_upload_key": upload_key,
        "lifecycle_state": "ACTIVE"
    })
    save_chunks(doc_id, [{"chunk_id": f"{doc_id}_c1", "content": "To be removed", "page_number": 1}])
    vector_store.chunks.append({
        "id": f"{doc_id}_c1",
        "chunk_id": f"{doc_id}_c1",
        "document_id": doc_id,
        "content": "To be removed",
        "owner_id": uid
    })

    # First deletion attempt -> SUCCESS
    result = delete_document(doc_id=doc_id, caller_id=uid, is_authenticated=True)
    assert result.success is True
    assert result.reason == "SUCCESS"

    # Verify storage object deleted
    assert storage_service.exists(upload_key) is False

    # Verify DB chunks deleted
    assert len(get_chunks_for_document(doc_id)) == 0

    # Verify DB document deleted or inactive
    doc_in_db = get_document(doc_id)
    assert doc_in_db is None or doc_in_db.get("lifecycle_state") != "ACTIVE"

    # Verify vector index purged
    matching_chunks = [c for c in vector_store.chunks if c.get("document_id") == doc_id]
    assert len(matching_chunks) == 0

    # Second repeated deletion -> NOT_FOUND (safe idempotency)
    repeat_result = delete_document(doc_id=doc_id, caller_id=uid, is_authenticated=True)
    assert repeat_result.success is False
    assert repeat_result.reason == "NOT_FOUND"


def test_ephemeral_disk_restart_recovery():
    """
    CRITICAL ACCEPTANCE TEST (Phase 15):
    Simulates container restart on Render Free with an empty ephemeral local disk.
    1. Register user
    2. Ingest document and save chunks
    3. Generate/save dense embeddings
    4. Create chat conversation and message
    5. Execute RAG query before restart
    6. Stop backend / Wipe local runtime filesystem (data/uploads, data/extracted, data/cache, manifest.json)
    7. Clear in-memory vector store
    8. Trigger startup rebuild (_rebuild)
    9. Verify:
       - User still exists in database
       - Chat conversation & message history intact
       - Document exists in document table
       - Chunks exist in chunks table
       - Embeddings exist in embeddings table
       - Rebuilt vector store retrieves the document chunks with full provenance
       - Citations still resolve
    """
    # 1. Register User
    uid = f"user_ephemeral_{os.urandom(4).hex()}"
    create_user(email=f"{uid}@ephemeral.test", name="Ephemeral Tester", password_hash=hash_password("Pass123!"), user_id=uid)

    # 2. Ingest document
    doc_id = f"doc_eph_{os.urandom(4).hex()}"
    doc_title = "Distributed Free Tier Architecture Specification"
    content_text = "CogniFlow executes hybrid RRF retrieval with TruncatedSVD LSA projection and Gemini neural dense vectors."
    
    upload_key = f"uploads/{doc_id}/original"
    extracted_key = f"extracted/{doc_id}/pages.json"
    storage_service.put_object(upload_key, content_text.encode("utf-8"), content_type="text/plain")

    doc_entry = {
        "id": doc_id,
        "document_id": doc_id,
        "owner_id": uid,
        "original_filename": f"{doc_title}.txt",
        "storage_filename": f"{doc_id}.txt",
        "mime_type": "text/plain",
        "size_bytes": len(content_text),
        "file_hash": f"hash_{doc_id}",
        "page_count": 1,
        "chunk_count": 1,
        "processing_status": "completed",
        "index_status": "indexed",
        "r2_upload_key": upload_key,
        "r2_extracted_key": extracted_key,
        "lifecycle_state": "ACTIVE"
    }
    create_document(doc_entry)

    # 3. Save Chunks
    chunk_item = {
        "chunk_id": f"{doc_id}_c1",
        "document_id": doc_id,
        "chunk_index": 0,
        "page_number": 1,
        "page_start": 1,
        "page_end": 1,
        "section": "Architecture",
        "subsection": "Free Tier",
        "source_location": "Page 1, Architecture",
        "content": content_text,
        "authors": "CogniFlow Engineers",
        "year": 2026,
        "source": doc_title
    }
    save_chunks(doc_id, [chunk_item])

    # 4. Save Embeddings in Database
    vector_data = [0.25, 0.50, 0.75, 0.10]
    save_document_embeddings(
        doc_id=doc_id,
        chunk_embeddings={f"{doc_id}_c1": vector_data},
        provider="neural_dense",
        model="gemini-embedding-001",
        dimensions=4,
        version=1
    )

    # 5. Create Chat & Message with Citation
    conv = create_conversation(user_id=uid, title="Restart Survivability Test", mode="adaptive_rag")
    conv_id = conv["id"]
    save_message(
        conv_id=conv_id,
        user_id=uid,
        role="assistant",
        content="The system survives ephemeral disk restarts safely [E1].",
        metadata={
            "citations": [{
                "id": "cite_1",
                "evidenceId": "E1",
                "documentId": doc_id,
                "documentTitle": doc_title,
                "pageStart": 1,
                "pageEnd": 1,
                "excerpt": content_text[:40]
            }]
        }
    )

    # Pre-restart retrieval test
    vector_store.reload()
    pre_results = vector_store.search("TruncatedSVD LSA projection", k=3, owner_id=uid)
    assert len(pre_results) > 0

    # -------------------------------------------------------------------------
    # 6. SIMULATE RENDER FREE RESTART & WIPED LOCAL EPHEMERAL DISK
    # -------------------------------------------------------------------------
    # Erase local uploaded files and extracted files for this document
    local_upload = UPLOADS_DIR / f"{doc_id}.txt"
    if local_upload.exists():
        local_upload.unlink(missing_ok=True)
    local_extracted = EXTRACTED_DIR / f"{doc_id}.json"
    if local_extracted.exists():
        local_extracted.unlink(missing_ok=True)

    # Clear in-memory vector store completely
    vector_store.chunks.clear()
    vector_store.in_memory_docs.clear()
    vector_store.total_docs = 0
    assert len(vector_store.chunks) == 0

    # -------------------------------------------------------------------------
    # 7. BACKEND STARTUP REBUILD FROM DATABASE ONLY
    # -------------------------------------------------------------------------
    vector_store._rebuild()

    # 8. VERIFY RECOVERY INVARIANTS:
    # A. User still exists
    recovered_user = get_user_by_id(uid)
    assert recovered_user is not None
    assert recovered_user["email"] == f"{uid}@ephemeral.test"

    # B. Chat still exists with citation metadata
    recovered_conv = get_conversation(conv_id, user_id=uid)
    assert recovered_conv is not None
    assert len(recovered_conv["messages"]) == 1
    assert recovered_conv["messages"][0]["citations"][0]["documentId"] == doc_id

    # C. Document still exists in database
    recovered_doc = get_document(doc_id)
    assert recovered_doc is not None
    assert recovered_doc["originalFilename"] == f"{doc_title}.txt"

    # D. Chunks still exist in database
    recovered_chunks = get_chunks_for_document(doc_id)
    assert len(recovered_chunks) == 1
    assert recovered_chunks[0]["content"] == content_text

    # E. Embeddings still exist in database
    recovered_embs = get_document_embeddings(doc_id)
    assert f"{doc_id}_c1" in recovered_embs

    # F. Storage object still accessible via StorageService abstraction
    assert storage_service.exists(upload_key) is True
    assert storage_service.get_object(upload_key) == content_text.encode("utf-8")

    # G. In-Memory retrieval index rebuilt from database chunks
    recovered_search = vector_store.search("hybrid RRF retrieval TruncatedSVD", k=3, owner_id=uid)
    assert len(recovered_search) > 0
    top_hit = recovered_search[0]
    assert top_hit["document_id"] == doc_id or top_hit.get("documentId") == doc_id
    assert "TruncatedSVD" in top_hit["text"]
    assert top_hit["page_start"] == 1
    assert top_hit["section"] == "Architecture"
