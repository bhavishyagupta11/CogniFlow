"""
Document Delete Authorization & Cross-User Isolation Regression Suite
Tests strict authorization policies for document operations:
1. Document Owner: User A deleting User A private document -> ALLOW (200)
2. Normal Authenticated User: User B deleting User A private document -> DENY (403/404)
3. Anti-Spoofing: User B spoofing x-user-id header with User A id -> DENY (403)
4. Anti-Spoofing: Unauthenticated caller claiming registered user id or admin -> DENY (401)
5. Target ID Guessing: User B using User A document ID -> DENY (403/404)
6. Guest/Dev Workspace: Guest deleting guest document -> ALLOW (200)
7. Guest/Dev Workspace: Guest deleting User A document -> DENY (403)
8. Public Document Protection: Neither normal user nor guest can delete public doc -> DENY (403)
9. Privileged Admin: Verified administrator can delete across users -> ALLOW (200)
10. Parity Verification: list, upload, reindex, delete use the same identity resolution path
"""

import io
from typing import Optional
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.db_service import create_user, init_db, get_db_connection
from backend.services.auth_service import hash_password, create_access_token
from backend.services.document_service import get_manifest, save_manifest, ingest_file
from backend.rag.vector_store import vector_store


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db_and_manifest():
    """Ensure clean test environment and database tables."""
    init_db()
    # Ensure test users exist
    alice = create_or_get_user("alice@cogniflow.test", "Alice User", "alice_pass123", "user_alice_test")
    bob = create_or_get_user("bob@cogniflow.test", "Bob User", "bob_pass123", "user_bob_test")
    admin = create_or_get_user("admin@cogniflow.test", "Admin User", "admin_pass123", "user_admin_test")
    yield


def create_or_get_user(email: str, name: str, password: str, user_id: str):
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ? OR email = ?", (user_id, email.lower())).fetchone()
        if row:
            return dict(row)
    pwd_hash = hash_password(password)
    return create_user(email=email, name=name, password_hash=pwd_hash, user_id=user_id)


def get_token_for(user_id: str, email: str, role: str = "user"):
    payload = {
        "sub": user_id,
        "email": email,
        "role": role
    }
    return create_access_token(payload)


import uuid

def upload_test_doc(user_id: str, filename: str, content: Optional[str] = None):
    """Helper to ingest a test text document directly with owner, ensuring unique SHA-256."""
    import asyncio
    if content is None:
        unique_token = uuid.uuid4().hex
        content = (
            f"# Authorization Test Document: {filename} - {unique_token}\n\n"
            f"This document is owned by user '{user_id}'. "
            "This document contains test data specifically formatted to validate cross-user isolation, "
            "prevent header spoofing, and test document deletion privileges across multiple tenants. "
            "It exceeds the minimum chunking threshold easily and provides structured content for indexing."
        )
    res = asyncio.run(ingest_file(
        file_bytes=content.encode("utf-8"),
        filename=filename,
        mime_type="text/plain",
        owner_id=user_id
    ))
    assert res.get("ok"), f"Failed to ingest test doc: {res}"
    return res["document"]["id"]


# ==============================================================================
# 1. User A deleting User A private document -> ALLOW
# ==============================================================================
def test_user_a_deletes_own_private_doc_allowed():
    doc_id = upload_test_doc("user_alice_test", "alice_private.txt")
    token_a = get_token_for("user_alice_test", "alice@cogniflow.test")

    resp = client.delete(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True

    # Verify deleted from manifest
    manifest = get_manifest()
    assert not any(m.get("id") == doc_id for m in manifest)


# ==============================================================================
# 2. User B deleting User A private document -> DENY
# ==============================================================================
def test_user_b_deletes_user_a_private_doc_denied():
    doc_id = upload_test_doc("user_alice_test", "alice_secret.txt")
    token_b = get_token_for("user_bob_test", "bob@cogniflow.test")

    resp = client.delete(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code in [403, 404], f"Expected 403/404 DENY, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is False

    # Verify Alice's document is preserved in manifest
    manifest = get_manifest()
    assert any(m.get("id") == doc_id for m in manifest), "Alice's document was incorrectly deleted!"


# ==============================================================================
# 3. User B spoofing x-user-id -> DENY
# ==============================================================================
def test_user_b_spoofing_x_user_id_denied():
    doc_id = upload_test_doc("user_alice_test", "alice_protected.txt")
    token_b = get_token_for("user_bob_test", "bob@cogniflow.test")

    # Bob presents Bob's token but headers claim to be Alice
    resp = client.delete(
        f"/api/documents/{doc_id}",
        headers={
            "Authorization": f"Bearer {token_b}",
            "x-user-id": "user_alice_test"
        }
    )
    assert resp.status_code == 403, f"Expected 403 Anti-Spoofing rejection, got {resp.status_code}: {resp.text}"
    assert "Spoofing detected" in resp.json().get("detail", "")

    # Verify doc remains safe
    manifest = get_manifest()
    assert any(m.get("id") == doc_id for m in manifest)


# ==============================================================================
# 4. Unauthenticated caller spoofing x-user-id -> DENY
# ==============================================================================
def test_unauthenticated_caller_spoofing_registered_user_denied():
    resp = client.delete(
        "/api/documents/some_doc_id",
        headers={"x-user-id": "user_alice_test"}
    )
    assert resp.status_code == 401, f"Expected 401 Unauthorized for unregistered user spoofing, got {resp.status_code}"


def test_unauthenticated_caller_spoofing_admin_denied():
    resp = client.delete(
        "/api/documents/some_doc_id",
        headers={"x-user-id": "admin"}
    )
    assert resp.status_code == 401, f"Expected 401 Unauthorized for unauthenticated admin spoofing, got {resp.status_code}"


# ==============================================================================
# 5. User B using User A document ID directly -> DENY
# ==============================================================================
def test_user_b_using_user_a_doc_id_denied():
    doc_id = upload_test_doc("user_alice_test", "alice_confidential.txt")
    token_b = get_token_for("user_bob_test", "bob@cogniflow.test")

    # Normal Bob request with Alice's doc_id
    resp = client.delete(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code in [403, 404]
    assert resp.json().get("ok") is False

    # Alice's doc remains untouched
    manifest = get_manifest()
    assert any(m.get("id") == doc_id for m in manifest)


# ==============================================================================
# 6. Guest/dev document deletion -> follow explicit guest workspace policy
# ==============================================================================
def test_guest_deletes_guest_document_allowed():
    doc_id = upload_test_doc("dev-user", "guest_sandbox.txt")

    # Guest request with no Authorization token
    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 200
    assert resp.json().get("ok") is True

    manifest = get_manifest()
    assert not any(m.get("id") == doc_id for m in manifest)


def test_guest_deleting_user_a_document_denied():
    doc_id = upload_test_doc("user_alice_test", "alice_secure.txt")

    # Guest attempts to delete User A doc
    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code in [403, 404]
    assert resp.json().get("ok") is False

    manifest = get_manifest()
    assert any(m.get("id") == doc_id for m in manifest)


# ==============================================================================
# 7. Public document protection
# ==============================================================================
def test_public_document_cannot_be_deleted_by_normal_user_or_guest():
    doc_id = upload_test_doc("system_public", "public_handbook.txt")
    admin_token = get_token_for("user_admin_test", "admin@cogniflow.test", role="admin")
    try:
        token_a = get_token_for("user_alice_test", "alice@cogniflow.test")

        # User A tries to delete public doc -> DENY
        resp_user = client.delete(
            f"/api/documents/{doc_id}",
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert resp_user.status_code == 403, f"Expected 403 for user deleting public doc, got {resp_user.status_code}"

        # Guest tries to delete public doc -> DENY
        resp_guest = client.delete(f"/api/documents/{doc_id}")
        assert resp_guest.status_code == 403, f"Expected 403 for guest deleting public doc, got {resp_guest.status_code}"

        # Public doc still exists
        manifest = get_manifest()
        assert any(m.get("id") == doc_id for m in manifest)
    finally:
        client.delete(f"/api/documents/{doc_id}", headers={"Authorization": f"Bearer {admin_token}"})


# ==============================================================================
# 8. Privileged administrator deletion -> ALLOW
# ==============================================================================
def test_privileged_admin_can_delete_any_document():
    doc_id = upload_test_doc("user_alice_test", "alice_to_be_moderated.txt")
    admin_token = get_token_for("user_admin_test", "admin@cogniflow.test", role="admin")

    resp = client.delete(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200, f"Expected 200 for admin deletion, got {resp.status_code}: {resp.text}"
    assert resp.json().get("ok") is True

    manifest = get_manifest()
    assert not any(m.get("id") == doc_id for m in manifest)


# ==============================================================================
# 9. Unified Identity Resolution Parity on list, upload, reindex, delete
# ==============================================================================
def test_unified_identity_resolution_parity():
    token_b = get_token_for("user_bob_test", "bob@cogniflow.test")
    doc_a = upload_test_doc("user_alice_test", "alice_parity.txt")

    # Anti-spoofing across all endpoints with Bob's token + x-user-id: user_alice_test
    spoof_headers = {
        "Authorization": f"Bearer {token_b}",
        "x-user-id": "user_alice_test"
    }

    # 1. LIST
    resp_list = client.get("/api/documents", headers=spoof_headers)
    assert resp_list.status_code == 403, f"List failed anti-spoofing: {resp_list.status_code}"

    # 2. UPLOAD
    fake_file = io.BytesIO(b"malicious spoofed content")
    resp_upload = client.post(
        "/api/documents",
        headers=spoof_headers,
        files={"file": ("spoofed.txt", fake_file, "text/plain")}
    )
    assert resp_upload.status_code == 403, f"Upload failed anti-spoofing: {resp_upload.status_code}"

    # 3. REINDEX
    resp_reindex = client.post(f"/api/documents/{doc_a}/reindex", headers=spoof_headers)
    assert resp_reindex.status_code == 403, f"Reindex failed anti-spoofing: {resp_reindex.status_code}"

    # 4. DELETE
    resp_del = client.delete(f"/api/documents/{doc_a}", headers=spoof_headers)
    assert resp_del.status_code == 403, f"Delete failed anti-spoofing: {resp_del.status_code}"


def test_cross_user_isolation_in_listing_and_reindexing():
    doc_a = upload_test_doc("user_alice_test", "alice_confidential_list.txt")
    token_b = get_token_for("user_bob_test", "bob@cogniflow.test")

    # Bob lists documents
    resp_list = client.get(
        "/api/documents",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp_list.status_code == 200
    docs = resp_list.json()
    bob_visible_ids = [d.get("id") for d in docs]
    assert doc_a not in bob_visible_ids, "Cross-user listing isolation failure: Alice's private doc is visible to Bob!"

    # Bob reindexes Alice's document
    resp_reindex = client.post(
        f"/api/documents/{doc_a}/reindex",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp_reindex.status_code == 403, f"Cross-user reindex isolation failure: got {resp_reindex.status_code}"


# ==============================================================================
# 10. Edge-Case Hardening: Unowned Document & Explicit Guest Workspace Tests
# ==============================================================================

def create_doc_with_owner(owner_id: Optional[str], filename: str, workspace: Optional[str] = None):
    """Helper to register a doc in manifest with custom owner_id and workspace."""
    doc_id = str(uuid.uuid4())
    doc_entry = {
        "id": doc_id,
        "document_id": doc_id,
        "filename": filename,
        "originalFilename": filename,
        "ownerId": owner_id,
        "owner_id": owner_id,
        "workspace": workspace,
        "indexStatus": "indexed",
        "size": 128
    }
    manifest = get_manifest()
    manifest.append(doc_entry)
    save_manifest(manifest)
    return doc_id


def test_guest_cannot_delete_unowned_document():
    """1. Guest -> target_owner=None -> DENY"""
    doc_id = create_doc_with_owner(None, "unowned_legacy_1.txt")
    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 403, f"Expected 403 for guest deleting unowned doc, got {resp.status_code}"
    assert resp.json().get("ok") is False
    manifest = get_manifest()
    assert any(m.get("id") == doc_id for m in manifest)


def test_normal_user_cannot_delete_unowned_document():
    """2. Normal user -> target_owner=None -> DENY"""
    doc_id = create_doc_with_owner(None, "unowned_legacy_2.txt")
    token_a = get_token_for("user_alice_test", "alice@cogniflow.test")
    resp = client.delete(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert resp.status_code == 403, f"Expected 403 for normal user deleting unowned doc, got {resp.status_code}"
    assert resp.json().get("ok") is False
    manifest = get_manifest()
    assert any(m.get("id") == doc_id for m in manifest)


def test_admin_can_delete_unowned_document():
    """3. Admin -> target_owner=None -> ALLOW if admin policy permits"""
    doc_id = create_doc_with_owner(None, "unowned_legacy_3.txt")
    admin_token = get_token_for("user_admin_test", "admin@cogniflow.test", role="admin")
    resp = client.delete(
        f"/api/documents/{doc_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 200, f"Expected 200 for admin deleting unowned doc, got {resp.status_code}"
    assert resp.json().get("ok") is True
    manifest = get_manifest()
    assert not any(m.get("id") == doc_id for m in manifest)


def test_guest_can_delete_explicit_guest_owned_document():
    """4. Guest -> target_owner='guest' -> ALLOW"""
    doc_id = create_doc_with_owner("guest", "explicit_guest_doc.txt")
    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 200, f"Expected 200 for guest deleting guest doc, got {resp.status_code}"
    assert resp.json().get("ok") is True
    manifest = get_manifest()
    assert not any(m.get("id") == doc_id for m in manifest)


def test_guest_can_delete_dev_user_owned_document():
    """5. Guest -> target_owner='dev-user' -> ALLOW"""
    doc_id = create_doc_with_owner("dev-user", "explicit_dev_user_doc.txt")
    resp = client.delete(f"/api/documents/{doc_id}")
    assert resp.status_code == 200, f"Expected 200 for guest deleting dev-user doc, got {resp.status_code}"
    assert resp.json().get("ok") is True
    manifest = get_manifest()
    assert not any(m.get("id") == doc_id for m in manifest)
