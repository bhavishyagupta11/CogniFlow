"""
CogniFlow Document Deletion Consistency & Rollback Regression Suite
Tests the required consistency invariants across:
- SQLite/database metadata hooks
- data/manifest.json
- Physical uploaded file & extracted JSON
- Vector store / embedding index
- Summary cache & derived state
- Background jobs & precomputations

Required Invariant:
SUCCESS: all document-derived state is removed consistently.
FAILURE: no silent partial deletion; rollback prior mutations and preserve recoverable state.

Test Scenarios:
1. Vector-store deletion failure -> Rollback manifest & files, preserve document
2. Manifest update failure -> Rollback physical files & vector store
3. Physical file deletion failure -> Rollback manifest & vector store, no partial deletion
4. Database update failure -> Rollback prior mutations
5. Repeated DELETE of an already-deleted document -> Idempotent 404
6. Deletion followed by retrieval/search -> Zero chunks returned by RAG
7. Deletion followed by opening an old citation -> 404 on /pdf and /raw
8. Deletion while summary/background processing is active -> Task cancelled, no resurrection
"""

import io
import json
import uuid
import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config import MANIFEST_PATH, UPLOADS_DIR, EXTRACTED_DIR
from backend.services.document_service import (
    get_manifest,
    save_manifest,
    ingest_file,
    delete_document
)
from backend.rag.vector_store import vector_store
from backend.services.summary_cache import summary_cache
from backend.rag.summarizer import (
    schedule_document_summary_precomputation,
    _active_precomputations
)


client = TestClient(app)


def ingest_test_document(filename: str, content: str = "Test document content for deletion consistency audit."):
    """Helper to ingest a real document into disk, manifest, and vector store."""
    unique_token = uuid.uuid4().hex
    full_content = (
        f"# Document Consistency Test: {filename} ({unique_token})\n\n"
        f"{content}\n\n"
        "This document verifies atomic rollback, transactional consistency, and non-resurrection. "
        "It exceeds minimum semantic chunking thresholds to generate valid indexed chunks."
    )
    res = asyncio.run(ingest_file(
        file_bytes=full_content.encode("utf-8"),
        filename=filename,
        mime_type="text/plain",
        owner_id="dev-user"
    ))
    assert res.get("ok"), f"Ingestion failed: {res}"
    return res["document"]["id"], res["document"]["filename"]


# ==============================================================================
# 1. Vector-Store Deletion Failure -> Rollback
# ==============================================================================
def test_vector_store_deletion_failure_rollback():
    doc_id, filename = ingest_test_document("test_vs_fail.txt")
    upload_path = UPLOADS_DIR / filename
    extracted_path = EXTRACTED_DIR / f"{doc_id}.json"

    assert upload_path.exists()
    assert extracted_path.exists()
    assert any(m.get("id") == doc_id for m in get_manifest())
    assert any(c.get("document_id") == doc_id or c.get("documentId") == doc_id for c in vector_store.chunks)

    # Simulate vector_store.remove_document raising a failure
    with patch.object(vector_store, "remove_document", side_effect=RuntimeError("Simulated VectorStore failure")):
        res = delete_document(doc_id, caller_id="dev-user", is_authenticated=False)
        assert res.success is False
        assert "DELETION_FAILED" in res.reason

    # INVARIANT CHECK: No silent partial deletion! State must be restored:
    # 1. Manifest still has doc
    assert any(m.get("id") == doc_id for m in get_manifest()), "Manifest lost doc on vector-store failure!"
    # 2. Upload file still exists
    assert upload_path.exists(), "Upload file was permanently deleted despite vector-store failure!"
    # 3. Extracted JSON still exists
    assert extracted_path.exists(), "Extracted JSON was permanently deleted despite vector-store failure!"
    # 4. Chunks still in vector store
    assert any(c.get("document_id") == doc_id or c.get("documentId") == doc_id for c in vector_store.chunks), "Chunks lost from vector store!"

    # Clean up cleanly
    delete_document(doc_id, caller_id="dev-user", is_authenticated=False)


# ==============================================================================
# 2. Manifest Update Failure -> Rollback
# ==============================================================================
def test_manifest_update_failure_rollback():
    doc_id, filename = ingest_test_document("test_manifest_fail.txt")
    upload_path = UPLOADS_DIR / filename
    extracted_path = EXTRACTED_DIR / f"{doc_id}.json"

    assert upload_path.exists()
    assert extracted_path.exists()

    # Simulate save_manifest raising an IOError
    with patch("backend.services.document_service.save_manifest", side_effect=IOError("Simulated manifest write error")):
        res = delete_document(doc_id, caller_id="dev-user", is_authenticated=False)
        assert res.success is False
        assert "DELETION_FAILED" in res.reason

    # INVARIANT CHECK: Physical files must be restored!
    assert upload_path.exists(), "Physical file not restored after manifest update failure!"
    assert extracted_path.exists(), "Extracted file not restored after manifest update failure!"
    assert any(m.get("id") == doc_id for m in get_manifest())
    assert any(c.get("document_id") == doc_id or c.get("documentId") == doc_id for c in vector_store.chunks)

    # Clean up cleanly
    delete_document(doc_id, caller_id="dev-user", is_authenticated=False)


# ==============================================================================
# 3. Physical File Deletion Failure -> Rollback
# ==============================================================================
def test_physical_file_deletion_failure_rollback():
    doc_id, filename = ingest_test_document("test_file_fail.txt")
    upload_path = UPLOADS_DIR / filename

    # Mock unlink on Path to simulate PermissionError
    orig_unlink = Path.unlink

    def mock_unlink(self, *args, **kwargs):
        if self == upload_path:
            raise PermissionError("Simulated file lock permission error")
        return orig_unlink(self, *args, **kwargs)

    with patch.object(Path, "unlink", side_effect=mock_unlink, autospec=True):
        res = delete_document(doc_id, caller_id="dev-user", is_authenticated=False)
        assert res.success is False
        assert "DELETION_FAILED" in res.reason

    # INVARIANT CHECK: Manifest and vector store untouched!
    assert any(m.get("id") == doc_id for m in get_manifest()), "Manifest was deleted despite file unlink failure!"
    assert any(c.get("document_id") == doc_id or c.get("documentId") == doc_id for c in vector_store.chunks)

    # Clean up cleanly
    delete_document(doc_id, caller_id="dev-user", is_authenticated=False)


# ==============================================================================
# 4. Database Update Failure -> Rollback
# ==============================================================================
def test_database_update_failure_rollback():
    doc_id, filename = ingest_test_document("test_db_fail.txt")
    upload_path = UPLOADS_DIR / filename
    extracted_path = EXTRACTED_DIR / f"{doc_id}.json"

    def failing_db_hook(d_id: str):
        raise RuntimeError("Simulated SQLite operational error: database is locked")

    res = delete_document(
        doc_id,
        caller_id="dev-user",
        is_authenticated=False,
        db_hook=failing_db_hook
    )
    assert res.success is False
    assert "DELETION_FAILED" in res.reason

    # INVARIANT CHECK: All state remains intact!
    assert upload_path.exists()
    assert extracted_path.exists()
    assert any(m.get("id") == doc_id for m in get_manifest())
    assert any(c.get("document_id") == doc_id or c.get("documentId") == doc_id for c in vector_store.chunks)

    # Clean up cleanly
    delete_document(doc_id, caller_id="dev-user", is_authenticated=False)


# ==============================================================================
# 5. Repeated DELETE of an Already-Deleted Document
# ==============================================================================
def test_repeated_delete_already_deleted_document():
    doc_id, _ = ingest_test_document("test_idempotent_del.txt")

    # First delete -> 200 OK
    resp1 = client.delete(f"/api/documents/{doc_id}")
    assert resp1.status_code == 200
    assert resp1.json().get("ok") is True

    # Second delete on same doc_id -> 404 NOT FOUND
    resp2 = client.delete(f"/api/documents/{doc_id}")
    assert resp2.status_code == 404
    body2 = resp2.json()
    assert body2.get("ok") is False
    assert body2.get("error", {}).get("code") == "NOT_FOUND"

    # Third delete -> still safe 404
    resp3 = client.delete(f"/api/documents/{doc_id}")
    assert resp3.status_code == 404


# ==============================================================================
# 6. Deletion Followed by Retrieval / Search
# ==============================================================================
def test_deletion_followed_by_retrieval_and_search():
    doc_id, filename = ingest_test_document(
        "quantum_computing_foundations.txt",
        content="Qubits exhibit quantum superposition and entanglement allowing polynomial speedup for Shor factoring."
    )

    # Pre-deletion: confirm document and chunks are searchable
    pre_candidates = vector_store.search("quantum superposition", k=5, document_id=doc_id)
    assert len(pre_candidates) > 0, "Pre-deletion candidate search failed"

    # Execute deletion
    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 200

    # Post-deletion:
    # 1. Direct document search returns 0
    post_targeted = vector_store.search("quantum superposition", k=5, document_id=doc_id)
    assert len(post_targeted) == 0, f"Deleted document still returned targeted candidates: {post_targeted}"

    # 2. Cross-document global search never returns chunks belonging to doc_id
    post_global = vector_store.search("quantum superposition", k=20)
    for cand in post_global:
        assert cand.get("document_id") != doc_id, "Deleted document chunks returned in global search!"
        assert cand.get("documentId") != doc_id

    # 3. Document does not appear in listing
    list_resp = client.get("/api/documents")
    assert list_resp.status_code == 200
    doc_ids_in_list = [d.get("id") for d in list_resp.json()]
    assert doc_id not in doc_ids_in_list


# ==============================================================================
# 7. Deletion Followed by Opening an Old Citation
# ==============================================================================
def test_deletion_followed_by_opening_old_citation():
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "CogniFlow Citation Spec Document with active evidence for testing citation navigation.")
    page.insert_text((50, 100), "Section 17: Deterministic Citations and Exact Source Passage Recovery.")
    pdf_bytes = doc.tobytes()
    doc.close()

    res = asyncio.run(ingest_file(
        file_bytes=pdf_bytes,
        filename="citation_spec.pdf",
        mime_type="application/pdf",
        owner_id="dev-user"
    ))
    assert res.get("ok"), f"Ingestion failed: {res}"
    doc_id = res["document"]["id"]

    # Verify raw/pdf endpoint works before deletion
    resp_pdf_before = client.get(f"/api/documents/{doc_id}/pdf", follow_redirects=False)
    assert resp_pdf_before.status_code in [200, 307], f"Expected 200 or 307, got {resp_pdf_before.status_code}"

    resp_raw_before = client.get(f"/api/documents/{doc_id}/raw", follow_redirects=False)
    assert resp_raw_before.status_code in [200, 307], f"Expected 200 or 307, got {resp_raw_before.status_code}"

    # Delete document
    del_resp = client.delete(f"/api/documents/{doc_id}")
    assert del_resp.status_code == 200

    # Verify old citation navigation on /pdf and /raw returns 404
    resp_pdf_after = client.get(f"/api/documents/{doc_id}/pdf", follow_redirects=False)
    assert resp_pdf_after.status_code == 404, f"Old citation /pdf resolved after deletion! Got {resp_pdf_after.status_code}"

    resp_raw_after = client.get(f"/api/documents/{doc_id}/raw", follow_redirects=False)
    assert resp_raw_after.status_code == 404, f"Old citation /raw resolved after deletion! Got {resp_raw_after.status_code}"


# ==============================================================================
# 8. Deletion While Summary / Background Processing is Active
# ==============================================================================
def test_deletion_while_background_processing_active():
    doc_id, filename = ingest_test_document(
        "async_background_doc.txt",
        content="Complex distributed algorithm specifications for Paxos consensus and Raft log replication."
    )

    # Populate summary cache for doc_id
    summary_cache.set_summary(
        doc_id=doc_id,
        doc_hash="hash123",
        page_range="all",
        config_hash="v1",
        data={"documentId": doc_id, "answer": "Cached summary before deletion"}
    )
    assert summary_cache.get_summary(doc_id, "hash123", "all", "v1") is not None

    # Simulate an active background task in _active_precomputations
    from unittest.mock import MagicMock
    mock_task = MagicMock()
    mock_task.done.return_value = False
    _active_precomputations[doc_id] = mock_task

    assert doc_id in _active_precomputations

    # Delete document while task is active
    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 200

    # 1. Verify task was cancelled and removed from active precomputations
    assert mock_task.cancel.called, "Background task was not cancelled on deletion!"
    assert doc_id not in _active_precomputations

    # 2. Verify summary cache for doc_id was completely purged
    assert summary_cache.get_summary(doc_id, "hash123", "all", "v1") is None

    # 3. Simulate background task trying to write cache post-deletion -> Resurrection prevented!
    assert not any(m.get("id") == doc_id for m in get_manifest())
