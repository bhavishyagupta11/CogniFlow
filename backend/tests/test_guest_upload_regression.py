"""
Regression Test Suite: Production Guest Document Upload & Persistence Invariants
Verifies:
1. Server-issued guest session creation.
2. Guest valid PDF upload succeeds without 'extracted_path' local variable errors.
3. Document appears in GuestSessionService with raw_bytes.
4. Chunks are created and added to in-memory vector store.
5. No durable DB document or DB chunks are created.
6. No Cloudflare R2 object upload occurs.
7. No durable extracted file or uploaded file written to disk for guest.
8. Raw PDF can be served to the guest via /api/documents/{doc_id}/raw.
9. PDF bytes begin with %PDF- and Content-Type is application/pdf.
10. Authenticated user upload still succeeds with durable R2/DB persistence.
11. Encrypted guest PDF upload succeeds with correct password and serves unlocked PDF bytes.
12. Encrypted PDF upload with wrong password remains rejected (HTTP 401).
13. Guest document remains viewable via /api/documents/{doc_id}/raw with HTTP Range support.
14. Guest document remains queryable and retrievable through RAG vector store search.
"""

import io
import fitz
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.db_service import db_service, create_user
from backend.services.auth_service import hash_password, create_access_token
from backend.services.guest_session_service import guest_session_service
from backend.services.storage_service import storage_service
from backend.rag.vector_store import vector_store
from backend.config import EXTRACTED_DIR, UPLOADS_DIR

client = TestClient(app)

SAMPLE_TEXT = (
    "Quantum Annealing and Adiabatic Optimization Architectures.\n"
    "This research paper provides an in-depth empirical investigation into quantum tunneling, "
    "energy landscapes, and hardware-accelerated combinatorial optimization algorithms."
)


def make_pdf(text: str = SAMPLE_TEXT) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def make_encrypted_pdf(password: str, text: str = SAMPLE_TEXT) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw=password,
        owner_pw=f"owner_{password}"
    )
    doc.close()
    return pdf_bytes


@pytest.fixture(autouse=True)
def clean_sessions():
    with guest_session_service._lock:
        guest_session_service._sessions.clear()
    yield


def test_guest_pdf_upload_zero_leakage_and_viewing():
    """
    Core Regression Test (Steps 1-9 & 13-14):
    1. Server-issued guest session.
    2. Valid PDF upload succeeds (no extracted_path crash).
    3. Document in GuestSessionService.
    4. Chunks created in memory.
    5. Zero durable DB records.
    6. Zero R2 uploads.
    7. Zero disk extracted files.
    8. Raw PDF served.
    9. Returns %PDF- bytes.
    13. Document viewable.
    14. Document searchable via RAG.
    """
    # 1. Server-issued guest session
    init_res = client.get("/api/auth/guest-session")
    assert init_res.status_code == 200
    session_id = init_res.json()["sessionId"]
    assert session_id.startswith("guest_")

    pdf_bytes = make_pdf()

    # Track R2 calls
    with patch.object(storage_service, "put_object", wraps=storage_service.put_object) as mock_r2_put:
        # 2. Upload valid PDF as guest
        upload_res = client.post(
            "/api/documents",
            headers={"x-session-id": session_id},
            files={"file": ("quantum_annealing.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        )

        # 3. Assert upload succeeds
        assert upload_res.status_code in [200, 201], f"Upload failed: {upload_res.text}"
        doc_data = upload_res.json()
        assert doc_data.get("ok") is True
        doc_id = doc_data["document"]["id"]

        # 4. Assert document appears in GuestSessionService with raw_bytes
        guest_doc = guest_session_service.get_document(session_id, doc_id)
        assert guest_doc is not None
        assert "raw_bytes" in guest_doc
        assert guest_doc["raw_bytes"].startswith(b"%PDF-")

        # 5. Assert chunks are created
        assert len(guest_doc.get("chunks", [])) >= 1
        assert guest_doc["page_count"] >= 1

        # 6. Assert no durable DB document is created
        assert db_service.get_document(doc_id) is None
        assert len(db_service.get_chunks_for_document(doc_id)) == 0

        # 7. Assert no R2 upload occurs
        assert mock_r2_put.call_count == 0, "Guest upload must never call R2 put_object"

        # Assert no durable extracted file or upload file on disk
        extracted_on_disk = EXTRACTED_DIR / f"{doc_id}.json"
        assert not extracted_on_disk.exists(), "Guest extracted JSON must not be written to disk"
        stored_on_disk = UPLOADS_DIR / f"{doc_id}.pdf"
        assert not stored_on_disk.exists(), "Guest uploaded PDF must not be written to disk"

        # 8 & 9. Assert raw PDF can be served and starts with %PDF-
        raw_res = client.get(
            f"/api/documents/{doc_id}/raw",
            headers={"x-session-id": session_id}
        )
        assert raw_res.status_code == 200
        assert raw_res.headers["content-type"] == "application/pdf"
        assert raw_res.content.startswith(b"%PDF-")
        assert raw_res.content == pdf_bytes

        # 13. Assert HTTP range request works for guest document
        range_res = client.get(
            f"/api/documents/{doc_id}/raw",
            headers={"x-session-id": session_id, "Range": "bytes=0-99"}
        )
        assert range_res.status_code == 206
        assert range_res.headers["content-type"] == "application/pdf"
        assert len(range_res.content) == 100
        assert range_res.content == pdf_bytes[:100]

        # 14. Assert document is queryable through RAG vector store
        rag_results = vector_store.search(
            query="quantum annealing tunneling",
            k=3,
            owner_id=session_id,
            document_id=doc_id,
            scope="DOCUMENT"
        )
        assert len(rag_results) >= 1
        assert any(r.get("document_id") == doc_id for r in rag_results)


def test_authenticated_upload_still_succeeds_with_durable_storage():
    """
    Test 10: Authenticated user upload still writes to durable storage (R2 / DB / disk).
    """
    import secrets
    email = f"auth_tester_{secrets.token_hex(4)}@cogniflow.test"
    pw_hash = hash_password("Password123!")
    user = create_user(email, pw_hash, "Auth Tester")
    token = create_access_token({"sub": user["id"], "email": email, "role": "user"})

    pdf_bytes = make_pdf(f"{SAMPLE_TEXT}\nAuthenticated enterprise document architecture.")

    with patch.object(storage_service, "put_object", wraps=storage_service.put_object) as mock_r2_put:
        upload_res = client.post(
            "/api/documents",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("auth_blueprint.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
        )
        assert upload_res.status_code in [200, 201]
        doc_id = upload_res.json()["document"]["id"]

        # Assert R2 was called for authenticated user (at least upload + extracted pages)
        assert mock_r2_put.call_count >= 1

        # Assert DB has document record
        db_doc = db_service.get_document(doc_id)
        assert db_doc is not None
        assert db_doc["owner_id"] == user["id"]


def test_encrypted_guest_pdf_flow():
    """
    Tests 11 & 12:
    11. Encrypted guest PDF succeeds with correct password and serves unlocked bytes.
    12. Wrong password is rejected with HTTP 401.
    """
    # 1. Guest session
    init_res = client.get("/api/auth/guest-session")
    session_id = init_res.json()["sessionId"]

    password = "CorrectHorseBatteryStaple"
    enc_bytes = make_encrypted_pdf(password=password)

    # 12. Upload with NO password -> 401 PASSWORD_REQUIRED
    res_no_pw = client.post(
        "/api/documents",
        headers={"x-session-id": session_id},
        files={"file": ("vault.pdf", io.BytesIO(enc_bytes), "application/pdf")}
    )
    assert res_no_pw.status_code == 401
    assert res_no_pw.json()["error"]["code"] == "PASSWORD_REQUIRED"

    # 12. Upload with WRONG password -> 401 INCORRECT_PASSWORD
    res_wrong_pw = client.post(
        "/api/documents",
        headers={"x-session-id": session_id},
        data={"password": "WrongPassword999"},
        files={"file": ("vault.pdf", io.BytesIO(enc_bytes), "application/pdf")}
    )
    assert res_wrong_pw.status_code == 401
    assert res_wrong_pw.json()["error"]["code"] == "INCORRECT_PASSWORD"

    # 11. Upload with CORRECT password -> 200 SUCCESS
    res_correct_pw = client.post(
        "/api/documents",
        headers={"x-session-id": session_id},
        data={"password": password},
        files={"file": ("vault.pdf", io.BytesIO(enc_bytes), "application/pdf")}
    )
    assert res_correct_pw.status_code in [200, 201]
    doc_id = res_correct_pw.json()["document"]["id"]

    # Verify document in GuestSessionService
    guest_doc = guest_session_service.get_document(session_id, doc_id)
    assert guest_doc is not None
    unlocked_bytes = guest_doc["raw_bytes"]
    assert unlocked_bytes.startswith(b"%PDF-")

    # Verify that the served bytes are unencrypted (can be opened without password)
    view_doc = fitz.open(stream=unlocked_bytes, filetype="pdf")
    assert not view_doc.is_encrypted, "Served PDF bytes must be unencrypted"
    assert "Quantum Annealing" in view_doc[0].get_text()
    view_doc.close()

    # Verify raw serving via API
    serve_res = client.get(
        f"/api/documents/{doc_id}/raw",
        headers={"x-session-id": session_id}
    )
    assert serve_res.status_code == 200
    assert serve_res.content.startswith(b"%PDF-")
    api_doc = fitz.open(stream=serve_res.content, filetype="pdf")
    assert not api_doc.is_encrypted
    api_doc.close()
