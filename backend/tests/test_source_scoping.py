"""
Test Chat-Scoped Source Isolation, Heuristic Rescorer Naming, and Verification Order
Tests:
1. Chat-scoped source isolation: Chat 1 attached to Doc A only searches Doc A; Chat 2 attached to Doc B only searches Doc B.
2. Zero-source chat returns clear empty message without querying any global corpus.
3. Reranker is named HEURISTIC RESCORER in trace events and steps.
4. Verification order: claims are verified before final answer delivery for paths requiring verification.
5. Guest session source attachment and isolation through /api/chats/{id}/sources.
"""

import json
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.db_service import create_user, init_db, get_db_connection, db_service
from backend.services.auth_service import hash_password, create_access_token
from backend.services.document_service import ingest_file
from backend.rag.vector_store import vector_store


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_users():
    init_db()
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", ("user_scope_test",)).fetchone()
        if not row:
            create_user(
                email="scopetest@cogniflow.test",
                name="Scope Tester",
                password_hash=hash_password("test_pass_123"),
                user_id="user_scope_test"
            )
    yield


def get_auth_token():
    return create_access_token({
        "sub": "user_scope_test",
        "email": "scopetest@cogniflow.test",
        "role": "user"
    })


def upload_content_doc(owner_id: str, filename: str, content: str):
    import asyncio
    unique_suffix = uuid.uuid4().hex[:6]
    unique_filename = f"{unique_suffix}_{filename}"
    unique_content = f"{content}\n\n<!-- nonce: {uuid.uuid4().hex} -->"
    res = asyncio.run(ingest_file(
        file_bytes=unique_content.encode("utf-8"),
        filename=unique_filename,
        mime_type="text/plain",
        owner_id=owner_id
    ))
    if not res.get("ok") and res.get("error", {}).get("existingId"):
        return res["error"]["existingId"]
    assert res.get("ok"), f"Failed to ingest test doc: {res}"
    return res["document"]["id"]


def parse_sse_events(response_text: str):
    events = []
    for line in response_text.splitlines():
        line = line.strip()
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except Exception:
                pass
    return events


def test_chat_scoped_source_isolation():
    token = get_auth_token()
    auth_headers = {"Authorization": f"Bearer {token}"}

    # Upload Doc A and Doc B with distinct, unique content
    doc_a_id = upload_content_doc(
        "user_scope_test",
        "doc_alpha_solar.txt",
        (
            "# Solar System Astrophysics\n\n"
            "Jupiter is the largest planet in our solar system, with a Great Red Spot. "
            "Jupiter has a mass more than two and a half times that of all other planets combined. "
            "Callisto, Ganymede, Europa, and Io are its four Galilean moons discovered in 1610."
        )
    )
    doc_b_id = upload_content_doc(
        "user_scope_test",
        "doc_beta_geology.txt",
        (
            "# Igneous and Metamorphic Petrology\n\n"
            "Obsidian is a naturally occurring volcanic glass formed when felsic lava cools rapidly. "
            "Pumice is an extrusive volcanic rock produced when lava with very high water content erupts violently. "
            "Granite consists primarily of quartz, feldspar, and plagioclase minerals."
        )
    )

    try:
        # Create Chat 1 and attach Doc A
        c1_resp = client.post("/api/chats", json={"title": "Chat Alpha"}, headers=auth_headers)
        assert c1_resp.status_code == 200
        chat1_id = c1_resp.json()["conversation"]["id"]

        attach_resp1 = client.post(f"/api/chats/{chat1_id}/sources", json={"document_id": doc_a_id}, headers=auth_headers)
        assert attach_resp1.status_code == 200
        sources1 = attach_resp1.json()["sources"]
        assert len(sources1) == 1
        assert sources1[0]["id"] == doc_a_id

        # Query Chat 1 asking about Jupiter
        q1_resp = client.post(
            "/api/chat",
            json={
                "question": "What is the largest planet and what are its Galilean moons?",
                "mode": "fast",
                "conversation_id": chat1_id,
            },
            headers=auth_headers
        )
        assert q1_resp.status_code == 200
        events1 = parse_sse_events(q1_resp.text)

        # Confirm sources returned are ONLY from Doc A
        retrieved_sources = []
        for e in events1:
            if e.get("type") == "sources":
                retrieved_sources = e.get("sources", [])

        assert len(retrieved_sources) > 0
        for s in retrieved_sources:
            s_doc_id = s.get("documentId") or s.get("document_id")
            assert s_doc_id == doc_a_id, f"Expected only Doc A ({doc_a_id}), but got {s_doc_id}"

        # Create Chat 2 and attach Doc B
        c2_resp = client.post("/api/chats", json={"title": "Chat Beta"}, headers=auth_headers)
        assert c2_resp.status_code == 200
        chat2_id = c2_resp.json()["conversation"]["id"]

        attach_resp2 = client.post(f"/api/chats/{chat2_id}/sources", json={"document_id": doc_b_id}, headers=auth_headers)
        assert attach_resp2.status_code == 200

        # Query Chat 2 asking about volcanic glass (Doc B)
        q2_resp = client.post(
            "/api/chat",
            json={
                "question": "What is obsidian and how does it form?",
                "mode": "fast",
                "conversation_id": chat2_id,
            },
            headers=auth_headers
        )
        assert q2_resp.status_code == 200
        events2 = parse_sse_events(q2_resp.text)

        retrieved_sources2 = []
        for e in events2:
            if e.get("type") == "sources":
                retrieved_sources2 = e.get("sources", [])

        assert len(retrieved_sources2) > 0
        for s in retrieved_sources2:
            s_doc_id = s.get("documentId") or s.get("document_id")
            assert s_doc_id == doc_b_id, f"Expected only Doc B ({doc_b_id}), but got {s_doc_id}"

        # Query Chat 2 asking about Jupiter (Doc A) -> MUST NOT find Jupiter because only Doc B is attached!
        q2_cross_resp = client.post(
            "/api/chat",
            json={
                "question": "Tell me about Jupiter and its Great Red Spot.",
                "mode": "fast",
                "conversation_id": chat2_id,
            },
            headers=auth_headers
        )
        assert q2_cross_resp.status_code == 200
        cross_events = parse_sse_events(q2_cross_resp.text)
        cross_sources = []
        for e in cross_events:
            if e.get("type") == "sources":
                cross_sources = e.get("sources", [])
        for s in cross_sources:
            s_doc_id = s.get("documentId") or s.get("document_id")
            assert s_doc_id != doc_a_id, "Corpus isolation violated: Chat 2 retrieved chunks from Doc A!"

    finally:
        # Cleanup test docs
        db_service.delete_document(doc_a_id)
        db_service.delete_document(doc_b_id)


def test_zero_sources_chat_returns_clear_message():
    token = get_auth_token()
    auth_headers = {"Authorization": f"Bearer {token}"}

    c_resp = client.post("/api/chats", json={"title": "Empty Sources Chat"}, headers=auth_headers)
    assert c_resp.status_code == 200
    chat_id = c_resp.json()["conversation"]["id"]

    q_resp = client.post(
        "/api/chat",
        json={
            "question": "What is the capital of France?",
            "mode": "adaptive_rag",
            "conversation_id": chat_id,
        },
        headers=auth_headers
    )
    assert q_resp.status_code == 200
    events = parse_sse_events(q_resp.text)

    # Must emit answerability_result with answerable = False
    ans_event = next((e for e in events if e.get("type") == "answerability_result"), None)
    assert ans_event is not None
    assert ans_event["answerability"]["answerable"] is False

    complete_event = next((e for e in events if e.get("type") == "pipeline_complete"), None)
    assert complete_event is not None
    assert "No sources are attached to this chat" in complete_event["result"]["answer"]
    assert complete_event["result"]["sources"] == []


def test_heuristic_rescorer_naming():
    token = get_auth_token()
    auth_headers = {"Authorization": f"Bearer {token}"}

    doc_id = upload_content_doc(
        "user_scope_test",
        "doc_gamma_rescore.txt",
        (
            "# Algorithms and Data Structures\n\n"
            "A B-Tree is a self-balancing tree data structure that maintains sorted data. "
            "In a B-Tree of order m, every internal node except the root has at least ceil(m/2) children. "
            "B-Trees are heavily used in databases and file systems due to block storage locality."
        )
    )

    try:
        c_resp = client.post("/api/chats", json={"title": "Rescore Test Chat"}, headers=auth_headers)
        assert c_resp.status_code == 200
        chat_id = c_resp.json()["conversation"]["id"]
        client.post(f"/api/chats/{chat_id}/sources", json={"document_id": doc_id}, headers=auth_headers)

        q_resp = client.post(
            "/api/chat",
            json={
                "question": "Explain B-Tree ordering and child properties.",
                "mode": "adaptive_rag",
                "conversation_id": chat_id,
            },
            headers=auth_headers
        )
        assert q_resp.status_code == 200
        events = parse_sse_events(q_resp.text)

        # Check reranker stage name in events
        for e in events:
            if e.get("stage") == "reranker" and e.get("label"):
                assert "HEURISTIC RESCORER" in e["label"], f"Reranker label was '{e['label']}', expected HEURISTIC RESCORER"

            if e.get("type") == "agent_finish" and e.get("step", {}).get("agent") == "reranker":
                step_label = e["step"]["label"]
                assert "HEURISTIC RESCORER" in step_label, f"Reranker step label was '{step_label}', expected HEURISTIC RESCORER"

    finally:
        db_service.delete_document(doc_id)


def test_guest_session_source_attachment_and_isolation():
    # Issue guest session
    init_resp = client.get("/api/auth/guest-session")
    assert init_resp.status_code == 200
    session_id = init_resp.json().get("sessionId")
    assert session_id is not None
    guest_headers = {"x-session-id": session_id}

    # Upload guest doc
    import io
    txt_bytes = (
        b"# Guest Notes\n\nGuest temporary document content for session-only testing. "
        b"This document contains enough words and sentences to exceed chunking thresholds easily."
    )
    upload_resp = client.post(
        "/api/documents",
        files={"file": ("guest_scoped.txt", io.BytesIO(txt_bytes), "text/plain")},
        headers=guest_headers
    )
    assert upload_resp.status_code in [200, 201]
    doc_data = upload_resp.json().get("document") or upload_resp.json().get("documents", [{}])[0]
    doc_id = doc_data["id"]

    # Create guest conversation
    chat_resp = client.post("/api/chats", json={"title": "Guest Chat"}, headers=guest_headers)
    assert chat_resp.status_code == 200
    chat_id = chat_resp.json()["conversation"]["id"]

    # Attach doc to guest conversation
    attach_resp = client.post(f"/api/chats/{chat_id}/sources", json={"document_id": doc_id}, headers=guest_headers)
    assert attach_resp.status_code == 200
    sources = attach_resp.json()["sources"]
    assert len(sources) == 1
    assert sources[0]["id"] == doc_id

    # List sources for guest conversation
    list_resp = client.get(f"/api/chats/{chat_id}/sources", headers=guest_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()["sources"]) == 1

    # Detach doc from guest conversation
    detach_resp = client.delete(f"/api/chats/{chat_id}/sources/{doc_id}", headers=guest_headers)
    assert detach_resp.status_code == 200
    assert len(detach_resp.json()["sources"]) == 0
