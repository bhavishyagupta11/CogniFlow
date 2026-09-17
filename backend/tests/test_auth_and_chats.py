"""
Tests for CogniFlow Authentication & Per-User Chat Persistence & Multi-User Isolation.
Verifies bcrypt password hashing, JWT authentication, per-user chat persistence,
and strict cross-user data isolation.
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.db_service import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    init_db()
    from backend.services.db_service import get_db_connection
    with get_db_connection() as conn:
        conn.execute("DELETE FROM messages WHERE user_id LIKE '%test%' OR user_id LIKE '%iso%' OR user_id LIKE 'user_%'")
        conn.execute("DELETE FROM conversations WHERE user_id LIKE '%test%' OR user_id LIKE '%iso%' OR user_id LIKE 'user_%'")
        conn.execute("DELETE FROM users WHERE email LIKE '%@cogniflow.test'")


def test_auth_registration_and_validation():
    # Invalid email
    res = client.post("/api/auth/register", json={
        "name": "Alice Tester",
        "email": "not-an-email",
        "password": "securePassword123"
    })
    assert res.status_code == 400
    assert "email" in res.json()["detail"].lower()

    # Short password
    res = client.post("/api/auth/register", json={
        "name": "Alice Tester",
        "email": "alice@cogniflow.test",
        "password": "123"
    })
    assert res.status_code == 400
    assert "at least 6 characters" in res.json()["detail"]

    # Valid registration
    res = client.post("/api/auth/register", json={
        "name": "Alice Tester",
        "email": "alice_registered@cogniflow.test",
        "password": "securePassword123"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert "token" in data
    assert data["user"]["email"] == "alice_registered@cogniflow.test"
    assert data["user"]["name"] == "Alice Tester"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]

    # Duplicate registration rejection
    res_dup = client.post("/api/auth/register", json={
        "name": "Alice Duplicate",
        "email": "alice_registered@cogniflow.test",
        "password": "anotherPassword456"
    })
    assert res_dup.status_code == 409
    assert "already exists" in res_dup.json()["detail"]


def test_auth_login_and_logout():
    # Register user
    email = "bob_login@cogniflow.test"
    pwd = "myPasswordBob789"
    client.post("/api/auth/register", json={
        "name": "Bob User",
        "email": email,
        "password": pwd
    })

    # Wrong password
    res_wrong = client.post("/api/auth/login", json={
        "email": email,
        "password": "wrongPassword123"
    })
    assert res_wrong.status_code == 401
    assert "invalid email or password" in res_wrong.json()["detail"].lower()

    # Correct login
    res_login = client.post("/api/auth/login", json={
        "email": email,
        "password": pwd
    })
    assert res_login.status_code == 200
    token = res_login.json()["token"]
    assert token is not None

    # Test /api/auth/me with valid token
    res_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me.status_code == 200
    assert res_me.json()["user"]["email"] == email

    # Test /api/auth/me without token
    res_unauth = client.get("/api/auth/me")
    assert res_unauth.status_code == 401

    # Test logout
    res_logout = client.post("/api/auth/logout")
    assert res_logout.status_code == 200


def test_chat_persistence_and_multi_user_isolation():
    """
    Critical Isolation Test:
    User A creates Chat A.
    User B creates Chat B.
    User B must NEVER see Chat A in chat list.
    User B must NEVER be able to read Chat A directly via GET /api/chats/{chatA_id}.
    User B must NEVER be able to delete Chat A or append messages to Chat A.
    """
    # 1. Register User A
    res_a = client.post("/api/auth/register", json={
        "name": "User Alpha",
        "email": "alpha_iso@cogniflow.test",
        "password": "AlphaPassword123"
    })
    token_a = res_a.json()["token"]
    user_a_id = res_a.json()["user"]["id"]

    # 2. Register User B
    res_b = client.post("/api/auth/register", json={
        "name": "User Beta",
        "email": "beta_iso@cogniflow.test",
        "password": "BetaPassword123"
    })
    token_b = res_b.json()["token"]
    user_b_id = res_b.json()["user"]["id"]

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 3. User A creates a conversation
    conv_a_res = client.post("/api/chats", headers=headers_a, json={
        "title": "Alpha Confidential Research",
        "mode": "deep_research"
    })
    assert conv_a_res.status_code == 200
    conv_a_id = conv_a_res.json()["conversation"]["id"]

    # 4. User A appends a user message and assistant message
    msg1_res = client.post(f"/api/chats/{conv_a_id}/messages", headers=headers_a, json={
        "role": "user",
        "content": "What is the Q3 net revenue for Company Alpha?"
    })
    assert msg1_res.status_code == 200

    msg2_res = client.post(f"/api/chats/{conv_a_id}/messages", headers=headers_a, json={
        "role": "assistant",
        "content": "Company Alpha net revenue was $4.2 billion in Q3 2024.",
        "metadata": {"confidence": 0.96, "sources": [{"documentId": "doc-alpha"}]}
    })
    assert msg2_res.status_code == 200

    # 5. User B creates their own conversation
    conv_b_res = client.post("/api/chats", headers=headers_b, json={
        "title": "Beta Public Notes",
        "mode": "fast_chat"
    })
    assert conv_b_res.status_code == 200
    conv_b_id = conv_b_res.json()["conversation"]["id"]

    # 6. Verify User B listing chats sees ONLY Chat B, NEVER Chat A
    list_b = client.get("/api/chats", headers=headers_b)
    assert list_b.status_code == 200
    b_conv_ids = [c["id"] for c in list_b.json()["conversations"]]
    assert conv_b_id in b_conv_ids
    assert conv_a_id not in b_conv_ids

    # 7. Verify User A listing chats sees ONLY Chat A, NEVER Chat B
    list_a = client.get("/api/chats", headers=headers_a)
    assert list_a.status_code == 200
    a_conv_ids = [c["id"] for c in list_a.json()["conversations"]]
    assert conv_a_id in a_conv_ids
    assert conv_b_id not in a_conv_ids

    # 8. User B attempts to access User A's conversation directly -> MUST FAIL with 404
    direct_access_b = client.get(f"/api/chats/{conv_a_id}", headers=headers_b)
    assert direct_access_b.status_code == 404
    assert "not authorized" in direct_access_b.json()["detail"].lower()

    # 9. User B attempts to delete User A's conversation -> MUST FAIL with 404
    delete_attempt_b = client.delete(f"/api/chats/{conv_a_id}", headers=headers_b)
    assert delete_attempt_b.status_code == 404

    # 10. User A can successfully load Chat A with all messages preserved in order
    direct_access_a = client.get(f"/api/chats/{conv_a_id}", headers=headers_a)
    assert direct_access_a.status_code == 200
    chat_a_data = direct_access_a.json()["conversation"]
    assert len(chat_a_data["messages"]) == 2
    assert chat_a_data["messages"][0]["role"] == "user"
    assert chat_a_data["messages"][0]["content"] == "What is the Q3 net revenue for Company Alpha?"
    assert chat_a_data["messages"][1]["role"] == "assistant"
    assert "4.2 billion" in chat_a_data["messages"][1]["content"]
    assert chat_a_data["messages"][1]["confidence"] == 0.96
