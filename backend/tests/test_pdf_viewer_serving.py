"""
Regression Test Suite: PDF Viewer & Document Serving Path
Covers:
1. Guest uploads valid PDF.
2. Guest can open/view the uploaded PDF (/api/documents/{id}/raw and /pdf).
3. PDF endpoint returns Content-Type 'application/pdf'.
4. PDF endpoint body begins with valid PDF bytes ('%PDF-').
5. Guest A cannot open Guest B's PDF (returns 403).
6. Arbitrary/forged session ID cannot access another guest's PDF (returns 403).
7. Authenticated user can open their persistent PDF.
8. Authenticated user cannot open another user's PDF (returns 403).
9. Guest PDF remains entirely outside R2 and durable database tables.
10. Guest PDF can still be queried through RAG retrieval.
11. Password-protected guest PDF can be opened after correct password and returns unlocked '%PDF-'.
12. Incorrect PDF password fails cleanly (401).
13. After guest-session migration, old guest session access is rejected.
14. Authenticated R2 storage behavior remains intact.
15. HTTP Range requests return 206 Partial Content, Content-Range, Accept-Ranges, and 416 on out-of-bounds.
"""

import io
import json
import secrets
import pytest
import fitz  # PyMuPDF
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.db_service import get_db_connection, create_user
from backend.services.auth_service import hash_password, create_access_token
from backend.services.guest_session_service import guest_session_service
from backend.services.storage_service import storage_service, R2StorageService
from backend.rag.vector_store import vector_store

client = TestClient(app)

SAMPLE_RESEARCH_TEXT = (
    "CogniFlow Adaptive Retrieval-Augmented Generation Architecture Overview.\n"
    "This document outlines the multi-agent orchestration framework, dense concept projections, "
    "and semantic chunking algorithms utilized across research tasks and evidence verification pipelines.\n"
    "It provides detailed experimental benchmarks, query classification routing, and citation grounding metrics."
)


def create_sample_pdf_bytes(extra_text: str = "") -> bytes:
    full_text = f"{SAMPLE_RESEARCH_TEXT}\n{extra_text}".strip()
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), full_text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_encrypted_pdf_bytes(extra_text: str = "", password: str = "secret123") -> bytes:
    full_text = f"{SAMPLE_RESEARCH_TEXT}\n{extra_text}".strip()
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), full_text)
    pdf_bytes = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw=password,
        owner_pw=f"owner_{password}"
    )
    doc.close()
    return pdf_bytes


@pytest.fixture(autouse=True)
def setup_clean_sessions():
    with guest_session_service._lock:
        guest_session_service._sessions.clear()
    yield


# ==============================================================================
# 1-4. Guest Upload and PDF Serving Tests
# ==============================================================================

def test_guest_upload_and_open_pdf_via_raw_and_pdf_endpoints():
    """
    1. Guest uploads valid PDF.
    2. Guest can open/view the uploaded PDF via /raw and /pdf.
    3. Content-Type is 'application/pdf'.
    4. Body begins with '%PDF-'.
    """
    resp = client.get("/api/auth/guest-session")
    session_id = resp.json()["sessionId"]

    pdf_bytes = create_sample_pdf_bytes("Research Paper Sample A")
    upload_resp = client.post(
        "/api/documents",
        headers={"x-session-id": session_id},
        files={"file": ("guest_research.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload_resp.status_code in [200, 201]
    doc_id = (upload_resp.json().get("document") or {}).get("id")
    assert doc_id is not None

    # Test 1: Open via /raw with x-session-id header
    raw_resp = client.get(f"/api/documents/{doc_id}/raw", headers={"x-session-id": session_id})
    assert raw_resp.status_code == 200
    assert "application/pdf" in raw_resp.headers.get("content-type", "")
    assert raw_resp.headers.get("accept-ranges") == "bytes"
    assert raw_resp.content.startswith(b"%PDF-")
    assert len(raw_resp.content) == len(pdf_bytes)

    # Test 2: Open via /pdf alias endpoint
    pdf_resp = client.get(f"/api/documents/{doc_id}/pdf", headers={"x-session-id": session_id})
    assert pdf_resp.status_code == 200
    assert "application/pdf" in pdf_resp.headers.get("content-type", "")
    assert pdf_resp.content.startswith(b"%PDF-")

    # Test 3: Open via query parameter ?session_id= (used by browser/PDF.js fallback)
    query_resp = client.get(f"/api/documents/{doc_id}/raw?session_id={session_id}")
    assert query_resp.status_code == 200
    assert "application/pdf" in query_resp.headers.get("content-type", "")
    assert query_resp.content.startswith(b"%PDF-")


# ==============================================================================
# 5-6. Guest Isolation & Security Tests
# ==============================================================================

def test_guest_a_cannot_open_guest_b_pdf():
    """
    5. Guest A cannot open Guest B's PDF (returns 403 Forbidden).
    """
    # Create Guest A
    resp_a = client.get("/api/auth/guest-session")
    session_a = resp_a.json()["sessionId"]

    # Create Guest B
    resp_b = client.get("/api/auth/guest-session")
    session_b = resp_b.json()["sessionId"]

    # Guest B uploads PDF
    pdf_b = create_sample_pdf_bytes("Confidential notes of Guest B with detailed architecture specifications.")
    upload_resp = client.post(
        "/api/documents",
        headers={"x-session-id": session_b},
        files={"file": ("b_notes.pdf", io.BytesIO(pdf_b), "application/pdf")}
    )
    assert upload_resp.status_code in [200, 201]
    doc_b_id = (upload_resp.json().get("document") or {}).get("id")
    assert doc_b_id is not None

    # Guest A attempts to open Guest B's PDF
    resp_hack = client.get(f"/api/documents/{doc_b_id}/raw", headers={"x-session-id": session_a})
    assert resp_hack.status_code == 403
    assert "Forbidden" in resp_hack.text

    # Guest B can open their own PDF normally
    resp_ok = client.get(f"/api/documents/{doc_b_id}/raw", headers={"x-session-id": session_b})
    assert resp_ok.status_code == 200
    assert resp_ok.content.startswith(b"%PDF-")


def test_arbitrary_or_forged_session_cannot_access_guest_pdf():
    """
    6. Arbitrary or forged session ID cannot access another guest's PDF.
    """
    # Create legitimate Guest
    resp = client.get("/api/auth/guest-session")
    legit_session = resp.json()["sessionId"]

    # Upload PDF
    pdf_bytes = create_sample_pdf_bytes("Secure File Data.")
    upload_resp = client.post(
        "/api/documents",
        headers={"x-session-id": legit_session},
        files={"file": ("secure_file.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload_resp.status_code in [200, 201]
    doc_id = (upload_resp.json().get("document") or {}).get("id")

    # Attacker tries arbitrary session header
    forged_session = "forged_attacker_session_12345"
    resp_attack = client.get(f"/api/documents/{doc_id}/raw", headers={"x-session-id": forged_session})
    assert resp_attack.status_code == 403

    # Attacker tries with no headers at all
    resp_anon = client.get(f"/api/documents/{doc_id}/raw")
    assert resp_anon.status_code == 403


# ==============================================================================
# 7-8. Authenticated User PDF Access & Cross-User Isolation
# ==============================================================================

def test_authenticated_user_access_and_cross_user_isolation():
    """
    7. Authenticated user can open their persistent PDF.
    8. Authenticated user cannot open another user's PDF (returns 403).
    """
    # Create User Alice
    email_alice = f"alice_{secrets.token_hex(4)}@cogniflow.test"
    pw_hash = hash_password("AlicePass123!")
    user_alice = create_user(email_alice, pw_hash, "Alice Research")
    token_alice = create_access_token({"sub": user_alice["id"], "email": email_alice, "role": "user"})

    # Create User Bob
    email_bob = f"bob_{secrets.token_hex(4)}@cogniflow.test"
    user_bob = create_user(email_bob, pw_hash, "Bob Analytics")
    token_bob = create_access_token({"sub": user_bob["id"], "email": email_bob, "role": "user"})

    # Alice uploads a persistent PDF
    pdf_alice = create_sample_pdf_bytes("Alice Persistent Research Paper with unique semantic content.")
    upload_resp = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token_alice}"},
        files={"file": ("alice_doc.pdf", io.BytesIO(pdf_alice), "application/pdf")}
    )
    assert upload_resp.status_code in [200, 201]
    doc_alice_id = (upload_resp.json().get("document") or {}).get("id")

    # 7. Alice can open her PDF
    alice_open = client.get(
        f"/api/documents/{doc_alice_id}/raw",
        headers={"Authorization": f"Bearer {token_alice}"},
        follow_redirects=False
    )
    assert alice_open.status_code in [200, 307]
    if alice_open.status_code == 200:
        assert alice_open.content.startswith(b"%PDF-")
    elif alice_open.status_code == 307:
        assert "r2.cloudflarestorage.com" in alice_open.headers.get("location", "")

    # Alice can also open via ?token= query parameter
    alice_query = client.get(f"/api/documents/{doc_alice_id}/raw?token={token_alice}", follow_redirects=False)
    assert alice_query.status_code in [200, 307]

    # 8. Bob cannot open Alice's PDF (403 Forbidden)
    bob_hack = client.get(
        f"/api/documents/{doc_alice_id}/raw",
        headers={"Authorization": f"Bearer {token_bob}"}
    )
    assert bob_hack.status_code == 403

    # Unauthenticated guest cannot open Alice's PDF (403 Forbidden)
    guest_hack = client.get(f"/api/documents/{doc_alice_id}/raw")
    assert guest_hack.status_code == 403


# ==============================================================================
# 9. Guest PDF Outside R2 and DB
# ==============================================================================

def test_guest_pdf_remains_entirely_outside_r2_and_durable_db():
    """
    9. Guest PDF remains entirely outside R2 and durable storage.
    """
    resp = client.get("/api/auth/guest-session")
    session_id = resp.json()["sessionId"]

    pdf_bytes = create_sample_pdf_bytes("Temporary isolated guest content.")
    upload_resp = client.post(
        "/api/documents",
        headers={"x-session-id": session_id},
        files={"file": ("temporary_guest_file.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload_resp.status_code in [200, 201]
    doc_id = (upload_resp.json().get("document") or {}).get("id")

    # Verify not written to SQLite documents table
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        assert row is None, "Guest document must NOT exist in persistent documents table"

    # Verify not in R2 object storage key
    r2_key = f"uploads/{doc_id}/original"
    assert not storage_service.exists(r2_key), "Guest PDF must NOT be written to R2 storage"


# ==============================================================================
# 10. Guest PDF Queried Through RAG
# ==============================================================================

def test_guest_pdf_can_still_be_queried_through_rag():
    """
    10. Guest PDF can still be queried through RAG.
    """
    resp = client.get("/api/auth/guest-session")
    session_id = resp.json()["sessionId"]

    pdf_bytes = create_sample_pdf_bytes("Quantum Annealing and Superconducting Flux Qubit Optimizations in CogniFlow.")
    upload_resp = client.post(
        "/api/documents",
        headers={"x-session-id": session_id},
        files={"file": ("quantum_research.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload_resp.status_code in [200, 201]
    doc_id = (upload_resp.json().get("document") or {}).get("id")

    # Search in vector store with guest owner_id
    results = vector_store.search("Quantum Annealing", k=3, owner_id=session_id)
    assert len(results) > 0
    assert any(r.get("document_id") == doc_id or r.get("documentId") == doc_id for r in results)


# ==============================================================================
# 11-12. Password-Protected PDF Handling
# ==============================================================================

def test_password_protected_guest_pdf_upload_and_viewing():
    """
    11. Password-protected guest PDF can be opened after correct password.
    12. Incorrect PDF password still fails cleanly.
    """
    resp = client.get("/api/auth/guest-session")
    session_id = resp.json()["sessionId"]

    pw = "AlphaVault2026"
    enc_pdf = create_encrypted_pdf_bytes("Encrypted Confidential Intelligence Data for Cryptography Research.", password=pw)

    # 1. Upload without password -> fails with 401 PASSWORD_REQUIRED
    resp_no_pw = client.post(
        "/api/documents",
        headers={"x-session-id": session_id},
        files={"file": ("vault.pdf", io.BytesIO(enc_pdf), "application/pdf")}
    )
    assert resp_no_pw.status_code == 401
    assert resp_no_pw.json()["error"]["code"] == "PASSWORD_REQUIRED"

    # 2. Upload with incorrect password -> fails with 401 INCORRECT_PASSWORD
    resp_wrong_pw = client.post(
        "/api/documents",
        headers={"x-session-id": session_id},
        data={"password": "wrong_password_xyz"},
        files={"file": ("vault.pdf", io.BytesIO(enc_pdf), "application/pdf")}
    )
    assert resp_wrong_pw.status_code == 401
    assert resp_wrong_pw.json()["error"]["code"] == "INCORRECT_PASSWORD"

    # 3. Upload with correct password -> succeeds
    resp_ok = client.post(
        "/api/documents",
        headers={"x-session-id": session_id},
        data={"password": pw},
        files={"file": ("vault.pdf", io.BytesIO(enc_pdf), "application/pdf")}
    )
    assert resp_ok.status_code in [200, 201]
    doc_id = (resp_ok.json().get("document") or {}).get("id")

    # 4. Open the PDF -> must serve valid unlocked PDF bytes (can be parsed by fitz without password)
    open_resp = client.get(f"/api/documents/{doc_id}/raw", headers={"x-session-id": session_id})
    assert open_resp.status_code == 200
    assert open_resp.content.startswith(b"%PDF-")

    # Verify the served PDF bytes are fully decrypted/unlocked
    served_doc = fitz.open(stream=open_resp.content, filetype="pdf")
    assert served_doc.needs_pass == 0, "Served PDF bytes must be unlocked and not require password"
    assert "Encrypted Confidential Intelligence Data" in served_doc[0].get_text()
    served_doc.close()


# ==============================================================================
# 13. Guest Migration Invalidation
# ==============================================================================

def test_guest_session_migration_rejects_old_guest_access():
    """
    13. After guest-session migration, old guest access is rejected.
    """
    # Guest session
    resp = client.get("/api/auth/guest-session")
    session_id = resp.json()["sessionId"]

    # Guest uploads PDF
    pdf_bytes = create_sample_pdf_bytes("Document to be migrated to persistent account.")
    upload_resp = client.post(
        "/api/documents",
        headers={"x-session-id": session_id},
        files={"file": ("migrated_doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload_resp.status_code in [200, 201]
    doc_id = (upload_resp.json().get("document") or {}).get("id")

    # Guest can view before migration
    pre_resp = client.get(f"/api/documents/{doc_id}/raw", headers={"x-session-id": session_id})
    assert pre_resp.status_code == 200

    # User registers and migrates guest session
    user_email = f"migrated_{secrets.token_hex(4)}@cogniflow.test"
    reg_resp = client.post(
        "/api/auth/register",
        json={"email": user_email, "password": "SecurePassword123!", "name": "Migrated User"}
    )
    token = reg_resp.json()["token"]

    migrate_resp = client.post(
        "/api/auth/migrate-guest-session",
        headers={"Authorization": f"Bearer {token}", "x-session-id": session_id}
    )
    assert migrate_resp.status_code == 200
    assert migrate_resp.json().get("migrated") is True

    # 13a. Old guest session attempts to open PDF -> rejected (403 Forbidden)
    old_guest_resp = client.get(f"/api/documents/{doc_id}/raw", headers={"x-session-id": session_id})
    assert old_guest_resp.status_code == 403

    # 13b. Authenticated user can open the migrated PDF
    user_resp = client.get(
        f"/api/documents/{doc_id}/raw",
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False
    )
    assert user_resp.status_code in [200, 307]
    if user_resp.status_code == 200:
        assert user_resp.content.startswith(b"%PDF-")
    elif user_resp.status_code == 307:
        assert "r2.cloudflarestorage.com" in user_resp.headers.get("location", "")


# ==============================================================================
# 14. Authenticated R2 Document Preserved
# ==============================================================================

def test_authenticated_r2_behavior_preserved():
    """
    14. Existing PDF viewer behavior for authenticated R2 documents remains unchanged.
    """
    user_email = f"r2user_{secrets.token_hex(4)}@cogniflow.test"
    user = create_user(user_email, hash_password("Pass123!"), "R2 User")
    token = create_access_token({"sub": user["id"], "email": user_email, "role": "user"})

    pdf_bytes = create_sample_pdf_bytes("Durable Document in Storage.")
    upload_resp = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("durable_file.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload_resp.status_code in [200, 201]
    doc_id = (upload_resp.json().get("document") or {}).get("id")

    resp = client.get(f"/api/documents/{doc_id}/raw", headers={"Authorization": f"Bearer {token}"}, follow_redirects=False)
    if isinstance(storage_service, R2StorageService):
        assert resp.status_code == 307
        assert "r2.cloudflarestorage.com" in resp.headers.get("location", "")
    else:
        assert resp.status_code == 200
        assert resp.content.startswith(b"%PDF-")


# ==============================================================================
# 15. HTTP Range Requests Support
# ==============================================================================

def test_http_range_request_support():
    """
    15. Range requests return 206 Partial Content, Content-Range, Accept-Ranges: bytes.
    Out of bounds returns 416.
    """
    resp = client.get("/api/auth/guest-session")
    session_id = resp.json()["sessionId"]

    pdf_bytes = create_sample_pdf_bytes("Range test document data content.")
    total_len = len(pdf_bytes)

    upload_resp = client.post(
        "/api/documents",
        headers={"x-session-id": session_id},
        files={"file": ("range_test.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload_resp.status_code in [200, 201]
    doc_id = (upload_resp.json().get("document") or {}).get("id")

    # 1. Partial content range: bytes=0-100
    range_resp = client.get(
        f"/api/documents/{doc_id}/raw",
        headers={"x-session-id": session_id, "Range": "bytes=0-100"}
    )
    assert range_resp.status_code == 206
    assert range_resp.headers.get("content-range") == f"bytes 0-100/{total_len}"
    assert range_resp.headers.get("content-length") == "101"
    assert len(range_resp.content) == 101
    assert range_resp.content == pdf_bytes[0:101]

    # 2. Suffix range: bytes=-50 (last 50 bytes)
    suffix_resp = client.get(
        f"/api/documents/{doc_id}/raw",
        headers={"x-session-id": session_id, "Range": "bytes=-50"}
    )
    assert suffix_resp.status_code == 206
    assert suffix_resp.headers.get("content-range") == f"bytes {total_len - 50}-{total_len - 1}/{total_len}"
    assert len(suffix_resp.content) == 50
    assert suffix_resp.content == pdf_bytes[-50:]

    # 3. Invalid out-of-bounds range: bytes=99999-100000 -> 416
    bad_range = client.get(
        f"/api/documents/{doc_id}/raw",
        headers={"x-session-id": session_id, "Range": "bytes=99999-100000"}
    )
    assert bad_range.status_code == 416
    assert bad_range.headers.get("content-range") == f"bytes */{total_len}"


# ==============================================================================
# 16. Conditional Request & Non-Conditional Cache Policy Tests (Prevent 304)
# ==============================================================================

def test_guest_pdf_conditional_request_and_cache_control_never_returns_304():
    """
    Verifies that guest PDF serving:
    Test 1: Normal request -> 200, application/pdf, starts %PDF-, Cache-Control: no-store
    Test 2: If-None-Match header -> returns 200 with full PDF body (never 304)
    Test 3: If-Modified-Since header -> returns 200 with full PDF body (never 304)
    Test 4: Range request bytes=0-99 -> 206, length 100, Content-Range present
    Test 5: Guest serving does not write to R2, local disk, or durable DB
    Test 6: Cross-guest isolation returns 403 Forbidden
    Test 7: Authenticated user R2 storage behavior remains unchanged
    """
    from backend.services.db_service import get_db_connection
    from backend.config import EXTRACTED_DIR, UPLOADS_DIR

    # Setup Guest A
    resp_a = client.get("/api/auth/guest-session")
    session_a = resp_a.json()["sessionId"]

    pdf_bytes = create_sample_pdf_bytes("Conditional request and non-cacheable guest document text.")
    upload_res = client.post(
        "/api/documents",
        headers={"x-session-id": session_a},
        files={"file": ("guest_research.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert upload_res.status_code in [200, 201]
    doc_id = upload_res.json()["document"]["id"]

    # Test 1: Normal request with no conditional headers
    norm_res = client.get(
        f"/api/documents/{doc_id}/raw",
        headers={"x-session-id": session_a}
    )
    assert norm_res.status_code == 200
    assert norm_res.headers["content-type"] == "application/pdf"
    assert norm_res.headers["content-disposition"].startswith("inline")
    assert "no-store" in norm_res.headers.get("cache-control", "").lower()
    assert norm_res.content.startswith(b"%PDF-")
    assert norm_res.content == pdf_bytes

    # Test 2: If-None-Match with arbitrary ETag -> must NEVER return 304
    etag_res = client.get(
        f"/api/documents/{doc_id}/raw",
        headers={
            "x-session-id": session_a,
            "If-None-Match": '"W/123456789abcdef"',
        }
    )
    assert etag_res.status_code == 200, f"Expected 200, got {etag_res.status_code} (must never return 304)"
    assert etag_res.headers["content-type"] == "application/pdf"
    assert etag_res.content.startswith(b"%PDF-")
    assert len(etag_res.content) == len(pdf_bytes)
    assert etag_res.content == pdf_bytes

    # Test 3: If-Modified-Since with HTTP date -> must NEVER return 304
    ims_res = client.get(
        f"/api/documents/{doc_id}/raw",
        headers={
            "x-session-id": session_a,
            "If-Modified-Since": "Wed, 21 Oct 2026 07:28:00 GMT",
        }
    )
    assert ims_res.status_code == 200, f"Expected 200, got {ims_res.status_code} (must never return 304)"
    assert ims_res.headers["content-type"] == "application/pdf"
    assert ims_res.content.startswith(b"%PDF-")
    assert len(ims_res.content) == len(pdf_bytes)
    assert ims_res.content == pdf_bytes

    # Test 4: Range request bytes=0-99 -> 206 Partial Content
    range_res = client.get(
        f"/api/documents/{doc_id}/raw",
        headers={
            "x-session-id": session_a,
            "Range": "bytes=0-99",
            "If-None-Match": '"W/cached-etag"',
        }
    )
    assert range_res.status_code == 206, f"Expected 206, got {range_res.status_code}"
    assert range_res.headers.get("content-range") == f"bytes 0-99/{len(pdf_bytes)}"
    assert len(range_res.content) == 100
    assert range_res.content == pdf_bytes[:100]

    # Test 5: Verify guest PDF serving does not write to R2, local disk, or durable DB
    assert not (EXTRACTED_DIR / f"{doc_id}.json").exists()
    assert not (UPLOADS_DIR / f"{doc_id}.pdf").exists()
    assert not storage_service.exists(f"uploads/{doc_id}/original")
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        assert row is None

    # Test 6: Verify cross-guest isolation still returns 403
    resp_b = client.get("/api/auth/guest-session")
    session_b = resp_b.json()["sessionId"]
    cross_res = client.get(
        f"/api/documents/{doc_id}/raw",
        headers={"x-session-id": session_b}
    )
    assert cross_res.status_code == 403

    # Test 7: Verify authenticated user R2 behavior remains unchanged
    user_email = f"r2_test_{secrets.token_hex(4)}@cogniflow.test"
    user = create_user(user_email, hash_password("Password123!"), "R2 Tester")
    token = create_access_token({"sub": user["id"], "email": user_email, "role": "user"})
    auth_upload = client.post(
        "/api/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("auth_r2.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    )
    assert auth_upload.status_code in [200, 201]
    auth_doc_id = auth_upload.json()["document"]["id"]

    auth_view = client.get(
        f"/api/documents/{auth_doc_id}/raw",
        headers={"Authorization": f"Bearer {token}"},
        follow_redirects=False
    )
    assert auth_view.status_code in [200, 307]
    if auth_view.status_code == 307:
        assert "r2.cloudflarestorage.com" in auth_view.headers.get("location", "")

