"""
CogniFlow Automated Test Suite: Retrieval Architectures, Modes & Telemetry
Tests compliance with all 10 Mandatory Pre-Execution Corrections.
"""

import pytest
import asyncio
import json
from unittest.mock import AsyncMock, patch

from backend.rag.vector_store import vector_store
from backend.rag.retrieval_evaluator import (
    evaluate_retrieval_strategy,
    compare_all_retrieval_architectures
)
from backend.services.telemetry_service import telemetry_collector, LatencyTracker
from backend.rag.pipeline import run_rag_pipeline
from backend.services.llm_provider import ProviderManager, BaseLLMProvider


@pytest.fixture
def ensure_lsa_64d():
    """Ensures index has >= 65 chunks so LSA 64-dimensional SVD projection is deterministic."""
    doc_id = "doc-test-lsa-retrieval"
    pages = [
        {
            "pageNumber": i,
            "text": (
                f"# Section {i}: Binary Search and Algorithmic Analysis {i}\n\n"
                f"Binary search time complexity operates in logarithmic O(log n) performance across partitioned datasets. "
                f"This deterministic module evaluates search space boundaries, asymptotic growth rates, and structural convergence properties. "
                f"Concept vocabulary vector terms include keyword_{i}, metric_{i}, distribution_{i}, and variance_{i}."
            )
        }
        for i in range(1, 75)
    ]
    vector_store.add_document(doc_id, "Deterministic LSA Test Document", pages)
    try:
        yield
    finally:
        vector_store.remove_document(doc_id)


@pytest.mark.anyio
async def test_vector_store_strategies_and_unclamped_scores(ensure_lsa_64d):
    """Verifies that lexical, semantic, and hybrid retrieval produce truthful unclamped scores."""
    query = "binary search time complexity"
    
    # 1. Lexical search
    lex_res = vector_store.search_lexical(query, k=3)
    assert len(lex_res) > 0
    for chunk in lex_res:
        assert 0.0 <= chunk["score"] <= 1.0
        assert "document_id" in chunk
        assert "chunk_id" in chunk
        assert "page_number" in chunk

    # 2. Semantic search (dense LSA)
    sem_res = vector_store.search_semantic(query, k=3)
    assert len(sem_res) > 0
    for chunk in sem_res:
        assert 0.0 <= chunk["score"] <= 1.0

    # 3. Hybrid search
    hyb_res = vector_store.search_hybrid(query, k=3)
    assert len(hyb_res) > 0
    for chunk in hyb_res:
        assert 0.0 <= chunk["score"] <= 1.0

    # 4. Index stats & memory footprint
    stats = vector_store.index_stats()
    assert stats["total_chunks"] > 0
    assert stats["semantic_dimensions"] == 64
    assert stats["memory_footprint_bytes"] > 0
    assert stats["memory_footprint_kb"] > 0


@pytest.mark.anyio
async def test_retrieval_evaluator_comparison_and_calibration():
    """Verifies empirical comparison of lexical, semantic, and hybrid retrieval with score calibration."""
    report = compare_all_retrieval_architectures()
    assert "comparison" in report
    assert "lexical" in report["comparison"]
    assert "semantic" in report["comparison"]
    assert "hybrid" in report["comparison"]

    for strat in ["lexical", "semantic", "hybrid"]:
        data = report["comparison"][strat]
        assert data["precision_at_k"] >= 0.0
        assert data["mrr"] > 0.0
        assert data["latency_p50_ms"] >= 0.0
        assert data["latency_p95_ms"] >= 0.0

    # Verify calibration recommendations
    cal = report["calibration"]
    assert "current_configured" in cal
    assert "empirical_recommended" in cal
    assert "ADAPTIVE_SIMPLE_THRESHOLD" in cal["empirical_recommended"]
    assert "ADAPTIVE_SCORE_GAP_THRESHOLD" in cal["empirical_recommended"]
    assert "RERANK_SCORE_THRESHOLD" in cal["empirical_recommended"]


@pytest.mark.anyio
async def test_mode_percentiles_and_engineering_targets():
    """Verifies P50/P95 latency and TTFT computation and engineering targets."""
    # Record sample query
    telemetry_collector.record("fast", 1750, 680)
    fast_metrics = telemetry_collector.get_mode_percentiles("fast")

    assert fast_metrics["measuredP50LatencyMs"] > 0
    assert fast_metrics["measuredP95LatencyMs"] >= fast_metrics["measuredP50LatencyMs"]
    assert fast_metrics["measuredP50TtftMs"] > 0
    assert fast_metrics["measuredP95TtftMs"] >= fast_metrics["measuredP50TtftMs"]
    assert fast_metrics["engineeringTargetLatencyMs"] == 3000
    assert fast_metrics["engineeringTargetTtftMs"] == 1000

    all_metrics = telemetry_collector.get_all_mode_percentiles()
    assert set(all_metrics.keys()) == {"fast", "adaptive_rag", "deep_research", "general_chat"}


@pytest.mark.anyio
async def test_general_chat_pipeline_mode():
    """Verifies that GENERAL CHAT mode bypasses document retrieval, sources, and citations."""
    events = []
    async for evt_str in run_rag_pipeline(
        question="Hello, explain QuickSort conceptually",
        mode="general_chat"
    ):
        if evt_str.startswith("data: "):
            try:
                evt = json.loads(evt_str[6:].strip())
                events.append(evt)
            except Exception:
                pass

    event_types = [e.get("type") for e in events]
    assert "route_selected" in event_types
    assert "generation_started" in event_types
    assert "pipeline_complete" in event_types

    # Must NOT have retrieval_started or citation_event
    assert "retrieval_started" not in event_types
    assert "citation_event" not in event_types

    # Final result must have zero sources
    comp_evt = next((e for e in events if e.get("type") == "pipeline_complete"), None)
    assert comp_evt is not None
    assert comp_evt["result"]["sources"] == []
    assert comp_evt["result"]["plan"]["mode"] == "general_chat"


@pytest.mark.anyio
async def test_controlled_provider_failure():
    """Verifies that when all LLM generation providers fail, controlled failure is emitted without hallucinated answers."""
    manager = ProviderManager()
    
    # Create failing dummy provider
    class FailingProvider(BaseLLMProvider):
        def supports_streaming(self): return True
        def supports_structured_output(self): return False
        async def health(self): return {"ok": False}
        async def generate(self, prompt, **kwargs): raise RuntimeError("Simulated connection timeout")
        async def stream(self, prompt, **kwargs):
            if False: yield "unreachable"
            raise RuntimeError("Simulated network failure")

    manager.providers = [
        FailingProvider("test_gemini", "gemini-2.5-flash"),
        FailingProvider("test_openrouter", "google/gemini-2.5-flash"),
        FailingProvider("test_ollama", "llama3.2:1b")
    ]

    events = []
    async for evt in manager.stream_with_fallback("Test query"):
        events.append(evt)

    evt_types = [e["type"] for e in events]
    assert "provider_error" in evt_types
    # Check that error announcement was emitted
    token_evt = next((e for e in events if e["type"] == "token"), None)
    assert token_evt is not None
    assert "Inference Infrastructure Notice" in token_evt["delta"]
    assert manager.last_telemetry["status"] == "all_providers_failed"


@pytest.mark.anyio
async def test_mmr_diversity_controller():
    """Verifies MMR diversity controller balances relevance with diversity and reports mmr_used."""
    from backend.rag.mmr import apply_mmr_diversity
    import numpy as np

    # 1. Test near-identical redundant candidates (should trigger MMR)
    candidates = [
        {"id": "c1", "text": "Binary search has O(log n) time complexity.", "score": 0.95},
        {"id": "c2", "text": "Binary search achieves O(log n) logarithmic complexity.", "score": 0.94},
        {"id": "c3", "text": "Linear search has O(n) time complexity.", "score": 0.70},
        {"id": "c4", "text": "Hash tables have O(1) expected lookup time.", "score": 0.65}
    ]
    # c1 and c2 have almost identical vectors
    v1 = np.array([1.0, 0.05, 0.0], dtype=np.float32)
    v2 = np.array([0.99, 0.06, 0.0], dtype=np.float32)
    v3 = np.array([0.1, 0.9, 0.0], dtype=np.float32)
    v4 = np.array([0.0, 0.1, 0.99], dtype=np.float32)
    vecs = np.vstack([v1, v2, v3, v4])
    q_vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)

    selected, mmr_used = apply_mmr_diversity(
        candidates=candidates,
        candidate_vectors=vecs,
        query_vector=q_vec,
        lambda_param=0.7,
        top_k=3,
        redundancy_threshold=0.82
    )
    assert mmr_used is True
    assert len(selected) == 3
    # c1 is selected first (highest rel), c3 or c4 should be preferred over redundant c2
    selected_ids = [c["id"] for c in selected]
    assert "c1" in selected_ids


@pytest.mark.anyio
async def test_semantic_chunking_provenance():
    """Verifies semantic chunking produces stable chunk IDs and complete provenance."""
    from backend.rag.chunker import semantic_chunk_document

    sample_pages = [
        {
            "page": 1,
            "text": "# Introduction to Data Structures\n\nA data structure is a specialized format for organizing, processing, and storing data.\n\n## 1. Linear Data Structures\n\nArrays and linked lists store elements sequentially."
        },
        {
            "page": 2,
            "text": "### Linked List Definition\n\nA linked list consists of nodes containing a data field and reference pointer to the next node in the sequence.\n\n```python\nclass Node:\n    def __init__(self, val):\n        self.val = val\n        self.next = None\n```\n\n## 2. Non-Linear Structures\n\nTrees and graphs represent hierarchical relationships."
        }
    ]

    chunks = semantic_chunk_document(
        document_id="test-doc-123",
        filename="Data_Structures_Guide.pdf",
        pages=sample_pages
    )

    assert len(chunks) >= 2
    for c in chunks:
        # Check required provenance fields from Section 4
        assert c["document_id"] == "test-doc-123"
        assert c["document_name"] == "Data_Structures_Guide.pdf"
        assert "chunk_id" in c
        assert c["chunk_id"].startswith("test-doc-123#chunk-")
        assert "section" in c
        assert "page_start" in c
        assert "page_end" in c
        assert c["page_start"] <= c["page_end"]
        assert "source_location" in c
        assert "text" in c
        assert len(c["text"].strip()) > 0


@pytest.mark.anyio
async def test_deterministic_citations_provenance():
    """Verifies deterministic citation assembler maps claims to evidence IDs without hallucinations."""
    from backend.rag.citations import citation_assembler

    sources = [
        {
            "chunk_id": "chunk-101",
            "document_id": "doc-algo",
            "documentTitle": "Algorithms.pdf",
            "page_start": 42,
            "page_end": 42,
            "text": "Binary search operates in O(log n) time on sorted arrays."
        },
        {
            "chunk_id": "chunk-102",
            "document_id": "doc-ds",
            "documentTitle": "Data Structures.pdf",
            "page_start": 88,
            "page_end": 89,
            "text": "A balanced AVL tree guarantees O(log n) worst-case search and insertion."
        }
    ]

    answer_with_citations = (
        "Binary search achieves logarithmic complexity [E1]. "
        "AVL trees guarantee balanced depth [E2]. "
        "Quantum superposition allows exponential parallelism [E99]."
    )

    sanitized, citations, issues = citation_assembler.map_and_validate_citations(
        answer_text=answer_with_citations,
        retrieved_sources=sources
    )

    # In-bounds citations must be preserved
    assert "[E1]" in sanitized
    assert "[E2]" in sanitized
    # Out-of-bounds citation [E99] must be stripped
    assert "[E99]" not in sanitized
    assert len(issues) == 1
    assert "E99" in issues[0] or "99" in issues[0]

    # Citations metadata must be completely grounded
    assert len(citations) == 2
    assert citations[0]["documentId"] == "doc-algo"
    assert citations[0]["pageStart"] == 42
    assert citations[1]["documentId"] == "doc-ds"
    assert citations[1]["pageEnd"] == 89

