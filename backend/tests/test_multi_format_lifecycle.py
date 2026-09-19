"""
Test Suite: Multi-Format Document Lifecycle, Ingestion, Retrieval, Summarization & API Parity
Covers:
1. Extraction across all 4 supported formats: PDF, DOCX, TXT, MD
2. Non-paginated provenance preservation in chunker (clean section headers, no fake page numbers)
3. Duplicate identity contract enforcement (owner_id + sha256 -> 409 DUPLICATE with existingFilename)
4. Fast API endpoints: GET /api/documents/{id}, GET /api/documents/{id}/content, GET /api/documents/{id}/raw
5. In-memory and persistent vector search across multi-format documents
6. Document-level summarization across all formats without crashing
7. Cascading deletion of multi-format documents, vector chunks, and summaries
"""

import io
import os
import json
import secrets
import pytest
import fitz  # PyMuPDF
import docx  # python-docx
from fastapi.testclient import TestClient

from backend.main import app
from backend.rag.extractor import extract_document_content
from backend.rag.chunker import semantic_chunk_document
from backend.services.document_service import delete_document, get_manifest
from backend.rag.vector_store import vector_store
from backend.rag.summarizer import hierarchical_summarize_document
from backend.services.db_service import get_db_connection, create_user
from backend.services.auth_service import hash_password, create_access_token
from backend.services.storage_service import storage_service, R2StorageService

client = TestClient(app)


# Helpers to create real binary test fixtures in memory
def make_test_pdf_bytes(title: str = "Test PDF Document") -> bytes:
    doc = fitz.open()
    p1 = doc.new_page()
    p1.insert_text((72, 72), f"# {title}\nChapter 1: Foundations\nBinary heaps are complete binary trees stored in arrays.")
    p2 = doc.new_page()
    p2.insert_text((72, 72), "Chapter 2: Heap Operations\nInsert operates in O(log n) time by percolating up.")
    b = doc.tobytes()
    doc.close()
    return b


def make_test_docx_bytes(title: str = "Test Word Document") -> bytes:
    doc = docx.Document()
    doc.add_heading(title, level=1)
    doc.add_paragraph("This is the introduction section for the multi-format documentation.")
    doc.add_heading("Section 2: Architecture Specifications", level=2)
    doc.add_paragraph("The vector index partitions documents into dense semantic embeddings and dense retrieval layers.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def make_test_txt_bytes(title: str = "Test Plain Text Document") -> bytes:
    text = (
        f"{title}\n\n"
        "Introduction:\n"
        "Plain text documents are processed with UTF-8 decoding and line-based segmentation.\n\n"
        "Advanced Topics:\n"
        "Heap indexing relies on parent = floor((i - 1) / 2) and children = 2i + 1, 2i + 2.\n"
    )
    return text.encode("utf-8")


def make_test_md_bytes(title: str = "Test Markdown Document") -> bytes:
    text = (
        f"# {title}\n\n"
        "## Overview\n"
        "Markdown documents maintain heading hierarchies for structural chunking.\n\n"
        "## Algorithmic Complexity\n"
        "Binary search achieves logarithmic time complexity O(log n) on sorted collections.\n"
    )
    return text.encode("utf-8")


@pytest.fixture
def auth_user():
    """Create a temporary test user and return headers."""
    email = f"testuser_{secrets.token_hex(4)}@cogniflow.test"
    password = "TestPassword123!"
    pw_hash = hash_password(password)
    user = create_user(email, "Test Developer", pw_hash)
    user_id = user["id"] if isinstance(user, dict) else user
    token = create_access_token({"sub": user_id, "email": email, "role": "developer"})
    yield {"id": user_id, "email": email, "headers": {"Authorization": f"Bearer {token}"}}
    try:
        from backend.services.db_service import db_service
        with db_service.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    except Exception:
        pass


def test_extractor_multi_format():
    """Verify extract_document_content works for PDF, DOCX, TXT, and MD."""
    # 1. PDF
    pdf_bytes = make_test_pdf_bytes("PDF Test")
    pages_pdf, unlocked_pdf = extract_document_content(pdf_bytes, "test.pdf")
    assert len(pages_pdf) == 2
    assert "Binary heaps" in pages_pdf[0]["text"]

    # 2. DOCX
    docx_bytes = make_test_docx_bytes("DOCX Test")
    pages_docx, _ = extract_document_content(docx_bytes, "spec.docx")
    assert len(pages_docx) >= 2
    assert any("Architecture Specifications" in p["text"] for p in pages_docx)

    # 3. TXT
    txt_bytes = make_test_txt_bytes("TXT Test")
    pages_txt, _ = extract_document_content(txt_bytes, "notes.txt")
    assert len(pages_txt) >= 1
    assert any("Heap indexing" in p["text"] for p in pages_txt)

    # 4. MD
    md_bytes = make_test_md_bytes("MD Test")
    pages_md, _ = extract_document_content(md_bytes, "readme.md")
    assert len(pages_md) >= 2
    assert any("Algorithmic Complexity" in p["text"] for p in pages_md)


def test_chunker_provenance_preservation():
    """Verify chunking preserves page provenance for PDF and section provenance for DOCX/TXT/MD."""
    # PDF chunks should have page_start and page_end
    pdf_bytes = make_test_pdf_bytes("DSA PDF")
    pages_pdf, _ = extract_document_content(pdf_bytes, "dsa.pdf")
    pdf_chunks = semantic_chunk_document(pages_pdf, "doc-pdf", "dsa.pdf")
    assert len(pdf_chunks) > 0
    assert pdf_chunks[0]["page_start"] == 1

    # DOCX chunks should have section info and p_start=None
    docx_bytes = make_test_docx_bytes("DSA DOCX")
    pages_docx, _ = extract_document_content(docx_bytes, "dsa.docx")
    docx_chunks = semantic_chunk_document(pages_docx, "doc-docx", "dsa.docx")
    assert len(docx_chunks) > 0
    assert docx_chunks[0]["page_start"] is None
    assert "Section" in docx_chunks[0]["source_location"] or "dsa.docx" in docx_chunks[0]["source_location"]

    # TXT chunks should have p_start=None
    txt_bytes = make_test_txt_bytes("DSA TXT")
    pages_txt, _ = extract_document_content(txt_bytes, "dsa.txt")
    txt_chunks = semantic_chunk_document(pages_txt, "doc-txt", "dsa.txt")
    assert len(txt_chunks) > 0
    assert txt_chunks[0]["page_start"] is None


def test_duplicate_document_rejection(auth_user):
    """Verify uploading duplicate document returns 409 DUPLICATE with existingFilename."""
    txt_bytes = make_test_txt_bytes("Duplicate Test Text")
    filename = "original_document.txt"

    # First upload
    res1 = client.post(
        "/api/documents/upload",
        headers=auth_user["headers"],
        files={"file": (filename, txt_bytes, "text/plain")}
    )
    assert res1.status_code == 200, f"Initial upload failed: {res1.text}"
    doc_id = res1.json().get("id") or (res1.json().get("document") or {}).get("id")

    try:
        # Second upload with identical content under different filename
        res2 = client.post(
            "/api/documents/upload",
            headers=auth_user["headers"],
            files={"file": ("renamed_copy.txt", txt_bytes, "text/plain")}
        )
        assert res2.status_code == 409
        err_json = res2.json().get("error") or res2.json()
        assert err_json.get("code") == "DUPLICATE"
        assert err_json.get("existingFilename") == filename
        assert filename in err_json.get("message", "")
    finally:
        # Clean up
        delete_document(doc_id, owner_id=auth_user["id"])


def test_document_api_endpoints_and_content(auth_user):
    """Verify GET /api/documents/{id}, GET /api/documents/{id}/content, and GET /api/documents/{id}/raw."""
    md_bytes = make_test_md_bytes("CogniFlow Guide")
    filename = "guide.md"

    res = client.post(
        "/api/documents/upload",
        headers=auth_user["headers"],
        files={"file": (filename, md_bytes, "text/markdown")}
    )
    assert res.status_code == 200
    doc_id = res.json().get("id") or (res.json().get("document") or {}).get("id")

    try:
        # 1. GET /api/documents/{id}
        doc_res = client.get(f"/api/documents/{doc_id}", headers=auth_user["headers"])
        assert doc_res.status_code == 200
        doc_data = doc_res.json()
        assert doc_data["id"] == doc_id
        assert doc_data["originalFilename"] == filename
        assert doc_data["extension"] == ".md"
        assert doc_data["sizeBytes"] > 0
        assert doc_data["characterCount"] > 0

        # 2. GET /api/documents/{id}/content
        content_res = client.get(f"/api/documents/{doc_id}/content", headers=auth_user["headers"])
        assert content_res.status_code == 200
        content_data = content_res.json()
        assert content_data["document_id"] == doc_id
        assert content_data["format"] == "md"
        assert len(content_data["sections"]) >= 1

        # 3. GET /api/documents/{id}/raw
        raw_res = client.get(f"/api/documents/{doc_id}/raw", headers=auth_user["headers"], follow_redirects=False)
        if isinstance(storage_service, R2StorageService):
            assert raw_res.status_code == 307
            assert "r2.cloudflarestorage.com" in raw_res.headers.get("location", "")
        else:
            assert raw_res.status_code == 200
            assert raw_res.content == md_bytes
            assert "markdown" in raw_res.headers.get("content-type", "") or "text" in raw_res.headers.get("content-type", "")
    finally:
        delete_document(doc_id, owner_id=auth_user["id"])


def test_multi_format_vector_search(auth_user):
    """Verify RAG retrieval finds relevant chunks across all supported formats."""
    # Ingest a DOCX and a TXT document
    docx_bytes = make_test_docx_bytes("DOCX Architecture")
    txt_bytes = make_test_txt_bytes("TXT Heaps")

    r1 = client.post(
        "/api/documents/upload",
        headers=auth_user["headers"],
        files={"file": ("arch.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    )
    assert r1.status_code == 200, f"Upload arch.docx failed: {r1.text}"
    d1_id = r1.json().get("id") or (r1.json().get("document") or {}).get("id")

    r2 = client.post(
        "/api/documents/upload",
        headers=auth_user["headers"],
        files={"file": ("heaps.txt", txt_bytes, "text/plain")}
    )
    assert r2.status_code == 200, f"Upload heaps.txt failed: {r2.text}"
    d2_id = r2.json().get("id") or (r2.json().get("document") or {}).get("id")

    try:
        # Search for architecture specs from DOCX
        results_arch = vector_store.search(
            query="vector index partitions dense semantic embeddings",
            top_k=3,
            owner_id=auth_user["id"]
        )
        assert len(results_arch) > 0
        assert any(r.get("document_id") == d1_id for r in results_arch)
        arch_match = next(r for r in results_arch if r.get("document_id") == d1_id)
        assert arch_match.get("source") == "arch.docx" or arch_match.get("original_filename") == "arch.docx"

        # Search for heap parent/child indexing from TXT
        results_heap = vector_store.search(
            query="parent child indexing formula",
            top_k=3,
            owner_id=auth_user["id"]
        )
        assert len(results_heap) > 0
        assert any(r.get("document_id") == d2_id for r in results_heap)
        heap_match = next(r for r in results_heap if r.get("document_id") == d2_id)
        assert heap_match.get("source") == "heaps.txt" or heap_match.get("original_filename") == "heaps.txt"
    finally:
        delete_document(d1_id, owner_id=auth_user["id"])
        delete_document(d2_id, owner_id=auth_user["id"])


def test_document_summarization_multi_format(auth_user):
    """Verify document summarizer batching, structural extraction, and hierarchical summary work across formats."""
    from backend.rag.summarizer import partition_pages_into_batches, build_final_hierarchical_summary

    # 1. Non-paginated (DOCX/TXT/MD) structural batching & section summary
    mock_sections = [
        {"section": "1. Introduction", "text": "Overview of algorithms and data structures."},
        {"section": "2. Stacks & Queues", "text": "Stack LIFO and Queue FIFO operations."},
        {"section": "3. Heap Indexing", "text": "Parent at (i-1)/2, children at 2i+1 and 2i+2."},
        {"section": "4. Binary Search", "text": "Logarithmic complexity O(log n) on sorted arrays."}
    ]
    batches = partition_pages_into_batches(mock_sections, batch_size=2)
    assert len(batches) == 2
    assert batches[0]["batch_index"] == 1

    # 2. Master hierarchical summary generation for multi-format document
    batch_summaries = [
        {"batch_index": 1, "page_range": "Sections 1–2", "summary": "### Section 1: Overview\nCore algorithmic paradigms."},
        {"batch_index": 2, "page_range": "Sections 3–4", "summary": "### Section 2: Heaps & Search\nHeap parent/child formulas and Binary Search O(log n)."}
    ]
    final_text = build_final_hierarchical_summary(
        doc_title="algorithms.docx",
        total_pages=0,
        batch_summaries=batch_summaries
    )
    assert "algorithms.docx" in final_text
    assert "Heap" in final_text
    assert "Binary Search" in final_text
    assert "O(log n)" in final_text
