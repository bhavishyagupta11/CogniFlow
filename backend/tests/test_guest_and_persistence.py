"""
Comprehensive Test Suite: Server-Issued Guest Identity, Isolation, Migration & PDF Password Handling
Verifies:
1. Server-issued guest session tokens (opaque, cryptographically random).
2. Anti-spoofing and rejection of client-chosen or arbitrary x-session-id values.
3. Strict session validation in GuestSessionService.
4. Complete guest isolation in-memory without database/storage leakage.
5. Zero pre-installed documents in baseline state.
6. Seamless guest-to-user migration (conversations, messages, documents, vector store ownership).
7. Password-protected PDF detection, rejection without password, rejection with incorrect password, and successful decryption.
8. Canonical AI identity prompt preservation across all modes.
"""

import io
import json
import secrets
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.db_service import init_db, get_db_connection, create_user
from backend.services.auth_service import hash_password, create_access_token
from backend.services.guest_session_service import guest_session_service
from backend.rag.vector_store import vector_store
from backend.services.document_service import get_manifest

client = TestClient(app)

SAMPLE_RESEARCH_TEXT = (
    "CogniFlow Adaptive Retrieval-Augmented Generation Architecture Overview.\n"
    "This document outlines the multi-agent orchestration framework, dense concept projections, "
    "and semantic chunking algorithms utilized across research tasks and evidence verification pipelines."
)


@pytest.fixture(autouse=True)
def setup_environment():
    """Ensure clean guest sessions before each test."""
    with guest_session_service._lock:
        guest_session_service._sessions.clear()
    yield


# ==============================================================================
# 1. Server-Issued Guest Session Identity Tests
# ==============================================================================

def test_first_anonymous_request_issues_cryptographic_guest_session():
    """
    On first anonymous request, backend creates a cryptographically random opaque
    guest session identifier and returns it in X-Session-ID header.
    """
    resp = client.get("/api/auth/guest-session")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    session_id = data.get("sessionId")
    assert session_id is not None
    assert session_id.startswith("guest_")
    # Must have sufficient cryptographic entropy (token_urlsafe(32) + prefix => >= 40 chars)
    assert len(session_id) >= 30
    assert resp.headers.get("X-Session-ID") == session_id

    # Verify backend associates it with GuestSessionService
    assert guest_session_service.is_valid_session(session_id)


def test_arbitrary_or_forged_x_session_id_is_rejected_and_never_adopted():
    """
    Backend must NEVER allow client to choose or use an arbitrary session ID.
    If client supplies an unknown x-session-id, backend discards it and issues a new server-authored session.
    """
    arbitrary_id = "attacker_chosen_custom_session_99999"
    resp = client.get("/api/auth/guest-session", headers={"x-session-id": arbitrary_id})
    assert resp.status_code == 200
    data = resp.json()
    issued_id = data.get("sessionId")

    # Client-supplied arbitrary token was NOT adopted
    assert issued_id != arbitrary_id
    assert issued_id.startswith("guest_")
    assert not guest_session_service.is_valid_session(arbitrary_id)
    assert guest_session_service.is_valid_session(issued_id)
    assert resp.headers.get("X-Session-ID") == issued_id


def test_arbitrary_x_session_id_on_documents_endpoint_is_rejected():
    """
    An arbitrary x-session-id supplied to /api/documents does not grant authority.
    Backend replaces it with a valid server-issued session ID in the response headers.
    """
    fake_session = "custom_fake_session_xyz"
    resp = client.get("/api/documents", headers={"x-session-id": fake_session})
    assert resp.status_code == 200
    server_session = resp.headers.get("X-Session-ID")
    assert server_session is not None
    assert server_session != fake_session
    assert server_session.startswith("guest_")
    assert guest_session_service.is_valid_session(server_session)
    assert not guest_session_service.is_valid_session(fake_session)


def test_active_server_issued_session_is_retained():
    """
    When client provides a valid, active server-issued session token,
    backend validates it and retains the session across requests.
    """
    # 1. Acquire valid session
    init_resp = client.get("/api/auth/guest-session")
    valid_session = init_resp.json().get("sessionId")

    # 2. Subsequent request with that session
    second_resp = client.get("/api/auth/guest-session", headers={"x-session-id": valid_session})
    assert second_resp.status_code == 200
    assert second_resp.json().get("sessionId") == valid_session
    assert second_resp.json().get("isNew") is False
    assert second_resp.headers.get("X-Session-ID") == valid_session


def test_unauthenticated_caller_cannot_spoof_registered_user_or_admin():
    """
    Unauthenticated caller attempting to send x-user-id claiming user or admin must get 401.
    """
    resp_user = client.get("/api/documents", headers={"x-user-id": "user_alice_test"})
    assert resp_user.status_code == 401

    resp_admin = client.get("/api/documents", headers={"x-user-id": "admin"})
    assert resp_admin.status_code == 401


# ==============================================================================
# 2. Zero Pre-Installed Documents & Clean Baseline
# ==============================================================================

def test_zero_preinstalled_documents_in_fresh_environment():
    """
    CogniFlow starts with 0 documents and 0 chunks.
    No pre-installed papers or corpus documents exist.
    """
    resp = client.get("/api/documents")
    assert resp.status_code == 200
    docs = resp.json()
    assert isinstance(docs, list)
    assert len(docs) == 0


# ==============================================================================
# 3. Guest Session Isolation & In-Memory Persistence Tests
# ==============================================================================

def test_guest_session_document_upload_and_strict_isolation():
    """
    Guest A uploads document -> Guest A sees it.
    Guest B cannot see Guest A's document.
    Guest A's document is NOT saved in persistent database tables.
    """
    # Create Guest A session
    resp_a = client.get("/api/auth/guest-session")
    session_a = resp_a.json()["sessionId"]

    # Create Guest B session
    resp_b = client.get("/api/auth/guest-session")
    session_b = resp_b.json()["sessionId"]

    assert session_a != session_b

    # Guest A uploads a document
    file_content = SAMPLE_RESEARCH_TEXT.encode("utf-8")
    upload_resp = client.post(
        "/api/documents",
        headers={"x-session-id": session_a},
        files={"file": ("guest_a_notes.txt", io.BytesIO(file_content), "text/plain")}
    )
    assert upload_resp.status_code in [200, 201, 202]
    doc_data = upload_resp.json().get("document") or upload_resp.json().get("documents", [{}])[0]
    doc_id = doc_data.get("id") or doc_data.get("document_id")
    assert doc_id is not None

    # Guest A lists documents -> sees guest_a_notes
    list_a = client.get("/api/documents", headers={"x-session-id": session_a}).json()
    assert any(d.get("id") == doc_id or d.get("document_id") == doc_id for d in list_a)

    # Guest B lists documents -> receives empty list (isolated!)
    list_b = client.get("/api/documents", headers={"x-session-id": session_b}).json()
    assert not any(d.get("id") == doc_id or d.get("document_id") == doc_id for d in list_b)

    # Guest B cannot delete Guest A's document
    del_resp = client.delete(f"/api/documents/{doc_id}", headers={"x-session-id": session_b})
    assert del_resp.status_code in [403, 404]

    # Verify zero durable writes in SQLite / Supabase tables for guest uploads
    with get_db_connection() as conn:
        doc_row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        assert doc_row is None, "Guest temporary document must NOT be written to durable documents table"
        chunk_rows = conn.execute("SELECT * FROM document_chunks WHERE document_id = ?", (doc_id,)).fetchall()
        assert len(chunk_rows) == 0, "Guest chunks must NOT be written to durable document_chunks table"


def test_guest_conversations_in_memory_isolation():
    """
    Guest conversations and messages remain in-memory and isolated per session.
    """
    resp_a = client.get("/api/auth/guest-session")
    session_a = resp_a.json()["sessionId"]

    resp_b = client.get("/api/auth/guest-session")
    session_b = resp_b.json()["sessionId"]

    # Guest A creates conversation
    create_resp = client.post(
        "/api/chats",
        headers={"x-session-id": session_a},
        json={"title": "Guest A Exploration", "mode": "adaptive_rag"}
    )
    assert create_resp.status_code == 200
    conv_id = create_resp.json()["conversation"]["id"]

    # Guest A sees it
    convs_a = client.get("/api/chats", headers={"x-session-id": session_a}).json()["conversations"]
    assert any(c["id"] == conv_id for c in convs_a)

    # Guest B does not see it
    convs_b = client.get("/api/chats", headers={"x-session-id": session_b}).json()["conversations"]
    assert not any(c["id"] == conv_id for c in convs_b)

    # Not persisted in database
    with get_db_connection() as conn:
        conv_row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,)).fetchone()
        assert conv_row is None, "Guest conversation must NOT be written to durable conversations table"


# ==============================================================================
# 4. Guest-to-User Migration Tests
# ==============================================================================

def test_guest_to_user_migration():
    """
    Seamlessly transfers temporary guest state (chats, messages, documents)
    to the newly authenticated user account.
    """
    # 1. Guest creates temporary session and state
    resp = client.get("/api/auth/guest-session")
    guest_session_id = resp.json()["sessionId"]

    # Guest creates conversation and sends message
    create_resp = client.post(
        "/api/chats",
        headers={"x-session-id": guest_session_id},
        json={"title": "Pre-login Mission", "mode": "fast"}
    )
    conv_id = create_resp.json()["conversation"]["id"]

    # Save message in guest session
    guest_session_service.save_message(
        session_id=guest_session_id,
        conv_id=conv_id,
        role="user",
        content="Important guest question before signup"
    )

    # Guest uploads a document
    file_content = SAMPLE_RESEARCH_TEXT.encode("utf-8")
    upload_resp = client.post(
        "/api/documents",
        headers={"x-session-id": guest_session_id},
        files={"file": ("guest_research.txt", io.BytesIO(file_content), "text/plain")}
    )
    doc_id = upload_resp.json().get("document", {}).get("id") or upload_resp.json().get("documents", [{}])[0].get("id")

    # 2. User registers an account
    user_email = f"migrated_user_{secrets.token_hex(4)}@cogniflow.test"
    reg_resp = client.post(
        "/api/auth/register",
        json={
            "name": "Migrated Tester",
            "email": user_email,
            "password": "Password123!",
            "confirm_password": "Password123!"
        }
    )
    assert reg_resp.status_code == 200
    user_token = reg_resp.json()["token"]
    user_id = reg_resp.json()["user"]["id"]

    # 3. Call guest migration
    migrate_resp = client.post(
        "/api/auth/migrate-guest-session",
        headers={
            "Authorization": f"Bearer {user_token}",
            "x-session-id": guest_session_id
        },
        json={"session_id": guest_session_id}
    )
    assert migrate_resp.status_code == 200
    migrate_data = migrate_resp.json()
    assert migrate_data.get("ok") is True
    assert migrate_data.get("migrated") is True
    assert migrate_data.get("conversationsMigrated") >= 1
    assert migrate_data.get("documentsMigrated") >= 1

    # 4. Verify conversation is now in user's durable account
    user_chats_resp = client.get("/api/chats", headers={"Authorization": f"Bearer {user_token}"})
    assert user_chats_resp.status_code == 200
    user_conv_ids = [c["id"] for c in user_chats_resp.json()["conversations"]]
    assert conv_id in user_conv_ids

    # 5. Verify document is now in user's durable account
    user_docs_resp = client.get("/api/documents", headers={"Authorization": f"Bearer {user_token}"})
    assert user_docs_resp.status_code == 200
    user_doc_ids = [d.get("id") or d.get("document_id") for d in user_docs_resp.json()]
    assert doc_id in user_doc_ids

    # 6. Idempotency: calling migration again returns migrated: False
    migrate_again_resp = client.post(
        "/api/auth/migrate-guest-session",
        headers={
            "Authorization": f"Bearer {user_token}",
            "x-session-id": guest_session_id
        },
        json={"session_id": guest_session_id}
    )
    assert migrate_again_resp.status_code == 200
    assert migrate_again_resp.json().get("migrated") is False

    # 7. Migrated session cannot be reused as an active guest session
    guest_reuse_resp = client.get("/api/auth/guest-session", headers={"x-session-id": guest_session_id})
    assert guest_reuse_resp.status_code == 200
    new_session_id = guest_reuse_resp.json()["sessionId"]
    assert new_session_id != guest_session_id, "Migrated session must NOT be reused as an active guest session"


# ==============================================================================
# 5. Encrypted PDF Password Handling Tests
# ==============================================================================

def create_test_encrypted_pdf(password: str) -> bytes:
    """Helper creating a valid encrypted PDF file in-memory using PyMuPDF with sufficient text."""
    import fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 72),
        "Protected internal memo for CogniFlow verification test.\n"
        "This is an encrypted document containing confidential research findings and architectural specifications.\n"
        "It verifies that encrypted PDF files require authentic credentials to decrypt and index into vector search."
    )
    pdf_bytes = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw=password,
        owner_pw="master_owner_key_999"
    )
    return pdf_bytes


def test_encrypted_pdf_missing_password_returns_401():
    """Uploading an encrypted PDF without a password returns 401 PASSWORD_REQUIRED."""
    encrypted_bytes = create_test_encrypted_pdf("SecurePdfPass!23")
    resp = client.post(
        "/api/documents",
        files={"file": ("protected_memo.pdf", io.BytesIO(encrypted_bytes), "application/pdf")}
    )
    assert resp.status_code == 401
    err = resp.json().get("error", {})
    assert err.get("code") == "PASSWORD_REQUIRED"


def test_encrypted_pdf_incorrect_password_returns_401():
    """Uploading an encrypted PDF with the wrong password returns 401 INCORRECT_PASSWORD."""
    encrypted_bytes = create_test_encrypted_pdf("CorrectPassword456")
    resp = client.post(
        "/api/documents",
        data={"password": "WrongPasswordAttempt"},
        files={"file": ("protected_memo.pdf", io.BytesIO(encrypted_bytes), "application/pdf")}
    )
    assert resp.status_code == 401
    err = resp.json().get("error", {})
    assert err.get("code") == "INCORRECT_PASSWORD"


def test_encrypted_pdf_correct_password_succeeds_and_does_not_persist_password():
    """
    Uploading an encrypted PDF with the correct password succeeds.
    The password is NOT saved to the database, manifest, or response body.
    """
    correct_pw = "UltraSecretVault789"
    encrypted_bytes = create_test_encrypted_pdf(correct_pw)
    resp = client.post(
        "/api/documents",
        data={"password": correct_pw},
        files={"file": ("protected_memo.pdf", io.BytesIO(encrypted_bytes), "application/pdf")}
    )
    assert resp.status_code in [200, 201, 202]
    res_data = resp.json()
    assert res_data.get("ok") is True

    # Ensure password is never included in the response
    res_str = json.dumps(res_data)
    assert correct_pw not in res_str, "Password must never appear in API responses"

    # Ensure password is never persisted in manifest
    manifest = get_manifest()
    manifest_str = json.dumps(manifest)
    assert correct_pw not in manifest_str, "Password must never be persisted in manifest"


# ==============================================================================
# 6. Canonical AI Identity Preservation Tests
# ==============================================================================

def test_canonical_ai_identity_prompt_preservation():
    """
    Verifies that CogniFlow's canonical developer attribution is present
    and preserved in system prompt configurations.
    """
    from backend.rag.identity import get_base_identity_prompt

    prompt = get_base_identity_prompt()
    assert "CogniFlow" in prompt
    assert "Bhavishya Gupta" in prompt
    assert "Google Gemini" in prompt
    # Must not contain unexposed model versions
    assert "gemini-1.5-pro-002" not in prompt
