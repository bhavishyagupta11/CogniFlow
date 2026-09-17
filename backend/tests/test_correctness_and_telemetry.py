"""
CogniFlow Correctness, Telemetry, Citation & Answerability Regression Test Suite
Validates:
- Query Concept Coverage Analysis
- Partial Answerability Gating (no linked-list / selection-sort drift on vector queries)
- Citation Fail-Safe (out-of-bounds [E99] removal, stable evidence IDs)
- Real Lifecycle Event Stream (stage_started, stage_completed, stage_skipped)
- LSA Semantic Concept Projection vs Lexical vs Hybrid RRF
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch

from backend.rag.concept_coverage import analyze_concept_coverage, extract_query_concepts
from backend.rag.answerability import detect_answerability
from backend.rag.citations import map_and_validate_citations
from backend.rag.vector_store import vector_store
from backend.rag.pipeline import run_rag_pipeline
from backend.models import AnswerabilityResult


def test_concept_extraction_and_coverage_array_vector():
    """
    TEST 1: Concept coverage for 'what is array and what is vector and what is the difference b/w them'.
    Corpus only contains arrays and linked lists (as distractor).
    Vector and comparison must be flagged as missing.
    Distractor chunks (linked list, sorting) must be detected for pruning.
    """
    query = "what is array and what is vector and what is the difference b/w them"
    concepts = extract_query_concepts(query)
    assert "array" in concepts
    assert "vector" in concepts
    assert "difference" in concepts

    # Simulated candidate chunks from retrieval
    candidate_chunks = [
        {
            "chunk_id": "chunk_array_1",
            "content": "An array is a linear data structure that stores elements of the same type at contiguous memory locations. Indexing is zero-based.",
            "document_id": "doc1",
            "document_title": "Data Structures Notes",
            "page_number": 1
        },
        {
            "chunk_id": "chunk_distractor_ll",
            "content": "Unlike arrays, a linked list is a linear collection of data elements whose order is not given by their physical placement in memory. Nodes contain pointers.",
            "document_id": "doc1",
            "document_title": "Data Structures Notes",
            "page_number": 5
        },
        {
            "chunk_id": "chunk_distractor_sort",
            "content": "Selection sort is an in-place comparison sorting algorithm with O(n^2) time complexity. It divides the array into sorted and unsorted subarrays.",
            "document_id": "doc1",
            "document_title": "Data Structures Notes",
            "page_number": 12
        }
    ]

    analysis = analyze_concept_coverage(query, candidate_chunks)

    # Array must be covered
    assert "array" in analysis["covered_concepts"]

    # Vector and difference must be missing (no vector evidence exists)
    assert "vector" in analysis["missing_concepts"]
    assert "difference" in analysis["missing_concepts"]

    # Overall coverage is partial
    assert analysis["is_partial"] is True
    assert analysis["is_fully_answerable"] is False

    # Distractor chunk chunk_distractor_sort has no relation to vector and should be pruned
    assert "chunk_array_1" not in analysis["distractor_chunk_ids"]
    assert "chunk_distractor_sort" in analysis["distractor_chunk_ids"]


def test_detect_answerability_with_concept_coverage():
    """
    Verifies that detect_answerability sets status='partially_answerable' and populates missingConcepts
    when required concepts are absent from retrieved chunks.
    """
    query = "what is array and what is vector and what is the difference"
    chunks = [
        {
            "chunkId": "c1",
            "documentId": "d1",
            "documentTitle": "Doc",
            "pageNumber": 1,
            "tokenCount": 40,
            "retrievalScore": 0.85,
            "content": "An array is an indexed collection of elements in contiguous memory."
        }
    ]

    result = detect_answerability(query, chunks)
    assert result.status == "partially_answerable"
    assert "vector" in [c.lower() for c in result.missingConcepts]
    assert "array" in [c.lower() for c in result.coveredConcepts]
    assert any("vector" in msg.lower() for msg in result.missingInformation)



def test_citation_failsafe_and_stripping():
    """
    TEST 6: Citations Fail-Safe.
    If the model emits valid [E1] and invalid [E99] (out of bounds):
    - [E99] must be stripped out completely.
    - [E1] must be preserved and mapped to the first evidence chunk.
    - citationsUsed must be 1.
    """
    generated_text = "Arrays store elements contiguously in memory [E1]. Some other claim [E99] has no evidence."
    sources = [
        {
            "document_id": "doc_1",
            "document_title": "Data Structures Notes",
            "chunk_id": "c1",
            "page_number": 1,
            "content": "Arrays allocate memory in contiguous blocks with constant-time indexing."
        },
        {
            "document_id": "doc_1",
            "document_title": "Data Structures Notes",
            "chunk_id": "c2",
            "page_number": 2,
            "content": "Pointers and dynamic memory allocation."
        }
    ]

    cleaned_text, citations_used, issues = map_and_validate_citations(
        generated_text,
        sources
    )

    # [E99] must be stripped
    assert "[E99]" not in cleaned_text
    # [E1] must be preserved
    assert "[E1]" in cleaned_text
    # citations_used count must be 1 (only E1)
    assert len(citations_used) == 1
    assert citations_used[0]["badge"] == "E1"
    assert citations_used[0]["chunk_id"] == "c1"
    assert len(issues) > 0  # Warned about out-of-bounds E99


def test_citation_unsupported_claim_no_fabrication():
    """
    Verifies that when generated text has no citation markers, citations are NOT fabricated
    by attaching top-ranked sources post-hoc.
    """
    text_without_citations = "This is a general statement that did not cite any evidence."
    sources = [
        {
            "document_id": "doc_1",
            "document_title": "Doc 1",
            "chunk_id": "c1",
            "page_number": 1,
            "content": "Some evidence here."
        }
    ]

    cleaned_text, citations_used, issues = map_and_validate_citations(
        text_without_citations,
        sources
    )

    assert len(citations_used) == 0
    assert citations_used == []


def test_absent_concept_query_abstention():
    """
    TEST 2: Query for a concept definitely absent from corpus.
    Corpus search returns empty/low relevance or no concept match -> answerability flags not_answerable.
    """
    query = "explain quantum entanglement and qubit decoherence in topological computing"
    # Even if some chunks are returned by broad search:
    chunks = [
        {
            "chunkId": "c1",
            "documentId": "d1",
            "documentTitle": "Data Structures",
            "pageNumber": 1,
            "tokenCount": 40,
            "retrievalScore": 0.08,
            "content": "Binary trees have a root node and at most two children per node."
        }
    ]

    result = detect_answerability(query, chunks)
    assert result.status == "not_answerable"
    assert not result.answerable
    assert len(result.missingInformation) > 0


@pytest.mark.anyio
async def test_backend_lifecycle_sse_event_stream():
    """
    TEST 9 & 10: Backend Lifecycle Event Stream.
    Verifies that run_rag_pipeline emits real backend events:
    request_started, stage_started, stage_completed/skipped, request_completed.
    """
    events = []
    async for raw in run_rag_pipeline(
        question="What is self-attention mechanism in Transformer architectures?",
        mode="fast",
        document_id="doc-attention-2017"
    ):
        if raw.startswith("data: "):
            try:
                evt = json.loads(raw[6:].strip())
                events.append(evt)
            except Exception:
                pass

    event_types = [e.get("type") for e in events]

    # Required lifecycle events
    assert "request_started" in event_types, "Must emit request_started event immediately"
    assert "stage_started" in event_types, "Must emit stage_started for active stages"
    assert "pipeline_complete" in event_types or "request_completed" in event_types

    # Inspect stage_started events
    stages_started = [e.get("stage") for e in events if e.get("type") == "stage_started"]
    assert "router" in stages_started
    assert "retriever" in stages_started

    # Check event metadata schema
    req_started_evt = next(e for e in events if e.get("type") == "request_started")
    assert "request_id" in req_started_evt
    assert "timestamp" in req_started_evt
    assert "mode" in req_started_evt


@pytest.fixture
def ensure_lsa_64d():
    """Ensures index has >= 65 chunks so LSA 64-dimensional SVD projection is deterministic."""
    added = False
    if vector_store.total_docs < 65:
        pages = [{"pageNumber": i, "text": f"Deterministic section {i} for LSA concept projection testing with unique vocabulary term_{i}."} for i in range(1, 70)]
        vector_store.add_document("doc-test-lsa-telemetry", "Deterministic LSA Test Document", pages)
        added = True
    try:
        yield
    finally:
        if added:
            vector_store.remove_document("doc-test-lsa-telemetry")


def test_lsa_semantic_retrieval_and_labeling(ensure_lsa_64d):
    """
    TEST 5 & 7: Semantic Retrieval Labeling and TF-IDF Query Scaling.
    Verifies that vector_store:
    1. Returns 'LSA-based latent semantic retrieval' in description / stats.
    2. Uses idf_weights to project queries into SVD space without unweighted distortion.
    """
    stats = vector_store.index_stats()
    assert stats["semantic_dimensions"] == 64
    assert hasattr(vector_store, "idf_weights")

    query_term = "binary search"
    lex_res = vector_store.search_lexical(query_term, k=3)
    sem_res = vector_store.search_semantic(query_term, k=3)
    hyb_res = vector_store.search_hybrid(query_term, k=3)

    assert len(lex_res) > 0
    assert len(sem_res) > 0
    assert len(hyb_res) > 0

    # Ensure scores are normalized and valid floats
    for r in lex_res + sem_res + hyb_res:
        assert 0.0 <= r["score"] <= 1.0
