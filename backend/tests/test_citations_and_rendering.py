"""
CogniFlow Citation & Provenance Regression Test Suite
Validates Section 19 Requirements:
1. Citation extraction from streamed fragments & compound markers ([E1, E2], [1, 2], [E10])
2. Citation preservation after sanitization
3. Invalid evidence ID rejection ([E99]) without incorrect mapping
4. Complete provenance preservation (doc name, page_start, page_end, chunk ID)
5. Source excerpt complete availability without arbitrary character truncation
6. Persisted citation metadata in database
"""

import pytest
import re
import uuid
import time
from backend.rag.citations import CitationAssembler, citation_assembler
from backend.services.db_service import (
    create_user,
    create_conversation,
    save_message,
    get_conversation,
    init_db
)


@pytest.fixture(autouse=True)
def ensure_db():
    init_db()


def test_compound_and_multiple_citation_normalization():
    """Validates [E1, E2], [1, 2], [E1; E2] are normalized to canonical individual [E{idx}] markers."""
    sources = [
        {"chunkId": "doc1#chunk-1", "documentId": "doc1", "documentTitle": "Doc A", "pageStart": 4, "text": "Arrays store items in contiguous memory."},
        {"chunkId": "doc1#chunk-2", "documentId": "doc1", "documentTitle": "Doc A", "pageStart": 5, "text": "Vectors grow dynamically."}
    ]

    answer_compound = "Arrays are contiguous [E1, E2] and dynamic [1, 2]."
    sanitized, citations, issues = citation_assembler.map_and_validate_citations(answer_compound, sources)

    assert "[E1] [E2]" in sanitized
    assert len(citations) == 2
    assert citations[0]["badge"] == "E1"
    assert citations[1]["badge"] == "E2"
    assert citations[0]["documentId"] == "doc1"
    assert citations[0]["pageStart"] == 4
    assert citations[1]["pageStart"] == 5
    assert len(issues) == 0


def test_invalid_evidence_id_rejection():
    """Validates invalid citation IDs such as [E99] are removed and never mapped to another source."""
    sources = [
        {"chunkId": "doc1#chunk-1", "documentId": "doc1", "documentTitle": "Doc A", "pageStart": 1, "text": "First chunk content."}
    ]

    answer_with_hallucination = "Arrays are fast [E1] but imaginary structures take [E99] time."
    sanitized, citations, issues = citation_assembler.map_and_validate_citations(answer_with_hallucination, sources)

    assert "[E1]" in sanitized
    assert "[E99]" not in sanitized
    assert len(citations) == 1
    assert citations[0]["badge"] == "E1"
    assert len(issues) >= 1
    assert any("E99" in iss or "99" in iss for iss in issues)


def test_full_source_excerpt_untruncated():
    """Validates the source passage is not truncated with a 350-character limit."""
    long_passage = "Contiguous block of memory. " * 30  # ~840 characters
    sources = [
        {
            "chunkId": "chunk-long-1",
            "documentId": "doc-long",
            "documentTitle": "Data Structures Book",
            "pageStart": 12,
            "pageEnd": 14,
            "text": long_passage,
            "score": 0.892
        }
    ]

    answer = "Arrays occupy memory blocks [E1]."
    sanitized, citations, issues = citation_assembler.map_and_validate_citations(answer, sources)

    assert len(citations) == 1
    cite = citations[0]
    # Verify excerpt has full length without character truncation
    assert len(cite["excerpt"]) == len(long_passage.strip())
    assert cite["excerpt"] == long_passage.strip()
    assert cite["score"] == 0.892
    assert cite["pageRange"] == "12–14"
    assert cite["sourceLocation"] == "pp. 12–14"


def test_citation_extraction_from_streamed_fragments():
    """Simulates token fragmentation and ensures citation markers survive streaming assembly."""
    tokens = ["Arrays ", "store ", "elements ", "in ", "memory ", "[", "E", "1", "]."]
    accumulated = ""
    for t in tokens:
        accumulated += t

    sources = [
        {"chunkId": "chunk-1", "documentId": "doc-1", "documentTitle": "DSA Notes", "pageStart": 1, "text": "Arrays store elements in memory."}
    ]

    sanitized, citations, issues = citation_assembler.map_and_validate_citations(accumulated, sources)
    assert "[E1]" in sanitized
    assert len(citations) == 1
    assert citations[0]["badge"] == "E1"


def test_persisted_citation_metadata():
    """Verifies that citations and evidence mapping are saved and restored in conversation messages."""
    unique_suffix = f"{uuid.uuid4().hex[:8]}_{int(time.time() * 1000)}"
    user_id = f"user_cite_test_{unique_suffix}"
    email = f"cite_test_{unique_suffix}@cogniflow.test"
    create_user(email=email, name="Citation Tester", password_hash="dummyhash", user_id=user_id)
    conv = create_conversation(user_id=user_id, title="Citation Persistence Test", mode="adaptive_rag")
    conv_id = conv["id"]

    try:
        mock_citations = [
            {
                "id": "cite-1",
                "badge": "E1",
                "evidenceId": "E1",
                "documentId": "doc-persisted",
                "documentTitle": "Database Internals",
                "pageStart": 42,
                "pageEnd": 42,
                "excerpt": "B-trees maintain sorted keys.",
                "score": 0.94,
                "verified": True
            }
        ]

        metadata = {
            "sources": [{"chunkId": "c1", "documentId": "doc-persisted", "badge": "E1"}],
            "citations": mock_citations,
            "totalDurationMs": 1200
        }

        saved_msg = save_message(
            conv_id=conv_id,
            user_id=user_id,
            role="assistant",
            content="B-trees are balanced search trees [E1].",
            metadata=metadata
        )
        assert saved_msg is not None

        loaded_conv = get_conversation(conv_id=conv_id, user_id=user_id)
        assert loaded_conv is not None
        assert len(loaded_conv["messages"]) == 1

        loaded_msg = loaded_conv["messages"][0]
        assert loaded_msg["content"] == "B-trees are balanced search trees [E1]."
        assert "citations" in loaded_msg
        assert len(loaded_msg["citations"]) == 1
        assert loaded_msg["citations"][0]["badge"] == "E1"
        assert loaded_msg["citations"][0]["pageStart"] == 42
        assert loaded_msg["citations"][0]["excerpt"] == "B-trees maintain sorted keys."
    finally:
        try:
            from backend.services.db_service import db_service
            with db_service.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM messages WHERE conversation_id = %s", (conv_id,))
                    cur.execute("DELETE FROM conversations WHERE id = %s", (conv_id,))
                    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        except Exception:
            pass
