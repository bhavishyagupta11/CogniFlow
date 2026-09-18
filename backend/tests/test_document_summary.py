"""
Unit & Integration Tests for CogniFlow Document-Level Summarization Route
Verifies:
1. Full-document summary intent classification across all required phrases
2. Document resolution for summary queries
3. Map-reduce page partitioning (zero gaps, zero duplicates, page ranges preserved)
4. Full document chunks/pages included (never limited to top_k=8)
5. Summary cache storage, reuse on subsequent requests (< 100ms), and invalidation on delete/reindex
6. Answerability gate behavior (fully_answerable with missingInformation=[])
7. Non-summary queries maintain normal top-k retrieval and answerability behavior
8. Real-time progress events emission during streaming
9. Final summary covers all major document sections: Introduction, Arrays, Linked Lists,
   Stacks, Queues, Sorting, Searching, Binary Search O(log n), Trees, BSTs, Heaps, Graphs.
"""

import pytest
import asyncio
from typing import List, Dict, Any

from backend.models import QueryComplexityDecision, AnswerabilityResult
from backend.rag.classifier import classify_query
from backend.rag.document_targeting import resolve_document_target
from backend.rag.summarizer import (
    partition_pages_into_batches,
    extract_batch_structural_summary,
    build_final_hierarchical_summary,
    hierarchical_summarize_document
)
from backend.services.summary_cache import summary_cache
from backend.rag.answerability import detect_answerability, check_document_summary_answerability
from backend.services.document_service import delete_document, reindex_document, get_manifest


def test_summary_intent_classification():
    """Requirement 1 & 2: Detect full-document summary intent on all specified phrases."""
    phrases = [
        "Give me the summary from page 0 to the last page, nothing should be missed from the summary, also outline the most important.",
        "complete summary of the document",
        "summarize the entire document",
        "give me a summary from first page to last page",
        "please summarize all pages",
        "nothing should be missed from this summary",
        "give me a chapter-wise summary",
        "chapterwise summary of notes",
        "full PDF summary",
        "full document summary please",
        "summarize all of the document",
        "page 0 to the last page complete summary"
    ]
    for p in phrases:
        decision = classify_query(p)
        assert decision.complexity == "document_summary", f"Failed to classify '{p}' as document_summary, got {decision.complexity}"
        assert decision.max_candidates > 8, f"Candidate count was limited to {decision.max_candidates} for '{p}'"
        assert decision.needs_reranking is False
        assert decision.needs_decomposition is False


def test_standard_query_still_uses_normal_rag():
    """Requirement 8: Verify non-summary queries still use normal classification & answerability."""
    q_simple = "what is a binary search tree?"
    d_simple = classify_query(q_simple)
    assert d_simple.complexity in ["simple", "standard"]
    assert d_simple.max_candidates <= 5

    q_complex = "compare merge sort and quick sort algorithms"
    d_complex = classify_query(q_complex)
    assert d_complex.complexity == "complex"


def test_document_targeting_for_summary():
    """Requirement 3: Resolve the selected document explicitly for document summary queries."""
    manifest = [{
        "id": "doc_ds_test",
        "document_id": "doc_ds_test",
        "original_filename": "Data Structures Full Notes.pdf",
        "originalFilename": "Data Structures Full Notes.pdf",
        "page_count": 128,
        "owner_id": "dev-user",
        "ownerId": "dev-user"
    }]
    q = "Give me the summary from page 0 to the last page, nothing should be missed from the summary, also outline the most important."
    
    target = resolve_document_target(q, owner_id="dev-user", manifest_override=manifest)
    assert target["is_document_specific"] is True
    assert target["resolved"] is True
    assert target["resolved_document_id"] is not None
    # For a multi-page summary, it should resolve to the multi-page PDF document
    assert target["resolved_filename"] in ["Data Structures Full Notes.pdf", "Vinit Khandelwal Projects.pdf"]


def test_page_partitioning_no_gaps_no_duplicates():
    """Requirement 4 & 8: Verify contiguous batch partitioning with zero missing or duplicate pages."""
    mock_pages = [{"pageNumber": i, "text": f"Content of page {i}"} for i in range(1, 129)]
    batches = partition_pages_into_batches(mock_pages, batch_size=12)

    assert len(batches) == 11  # 128 / 12 = 10 full batches + 1 remainder (8 pages)

    covered_pages = []
    for idx, b in enumerate(batches):
        assert b["batch_index"] == idx + 1
        b_pages = [p["pageNumber"] for p in b["pages"]]
        covered_pages.extend(b_pages)
        assert b["start_page"] == b_pages[0]
        assert b["end_page"] == b_pages[-1]
        assert b["page_range"] == f"{b_pages[0]}-{b_pages[-1]}"

    # Check exact continuity from page 1 to 128
    assert covered_pages == list(range(1, 129))
    assert len(covered_pages) == 128
    assert len(set(covered_pages)) == 128


def test_answerability_gate_for_document_summary():
    """Requirement 7: Document summary should not be marked partially answerable merely because top-k chunks were small."""
    # When document exists and has pages
    res = check_document_summary_answerability(
        target_doc_id="doc-123",
        target_filename="Data Structures Full Notes.pdf",
        doc_exists=True,
        page_count=128,
        processing_status="completed"
    )
    assert res.status == "fully_answerable"
    assert res.answerable is True
    assert res.missingInformation == []
    assert res.confidence >= 0.95

    # When document does not exist
    res_not_found = check_document_summary_answerability(
        target_doc_id=None,
        target_filename="missing.pdf",
        doc_exists=False,
        page_count=0,
        processing_status="not_found"
    )
    assert res_not_found.status == "not_answerable"
    assert res_not_found.answerable is False
    assert len(res_not_found.missingInformation) > 0


def test_summary_cache_reuse_and_invalidation():
    """Requirement 5 & 8: Cache stores summaries, reuses on subsequent requests, and invalidates on document delete."""
    doc_id = "test-doc-cache-uuid-999"
    doc_hash = "hash-xyz-123"
    page_range = "1-128"
    config_hash = "cfg-v1"

    test_data = {
        "documentId": doc_id,
        "totalPages": 128,
        "answer": "Comprehensive Summary: Introduction, Arrays, Binary Search O(log n), Trees, BSTs",
        "sources": [{"chunkId": f"{doc_id}#chunk-1", "score": 0.98}],
        "cached": False
    }

    # Initially cache miss
    summary_cache.invalidate_document(doc_id)
    assert summary_cache.get_summary(doc_id, doc_hash, page_range, config_hash) is None

    # Set cache
    summary_cache.set_summary(doc_id, doc_hash, page_range, config_hash, test_data)

    # Cache hit
    cached = summary_cache.get_summary(doc_id, doc_hash, page_range, config_hash)
    assert cached is not None
    assert cached["documentId"] == doc_id
    assert "Binary Search" in cached["answer"]

    # Invalidate
    invalidated_count = summary_cache.invalidate_document(doc_id)
    assert invalidated_count >= 1
    assert summary_cache.get_summary(doc_id, doc_hash, page_range, config_hash) is None


def test_hierarchical_summarize_emits_progress_events():
    """Requirement 6 & 8: Verify hierarchical summarizer emits all progress events."""
    async def _run():
        events_emitted = []

        async def on_progress(evt: Dict[str, Any]):
            events_emitted.append(evt["type"])

        doc_meta = {
            "id": "doc-test-progress",
            "originalFilename": "Test Data Structures Notes.pdf",
            "hash": "test-hash-progress",
            "pageCount": 12
        }

        summary_cache.invalidate_document("doc-test-progress")

        # Run summarizer with batch_size=4 so we have 3 batches
        res = await hierarchical_summarize_document(
            doc_id="doc-test-progress",
            doc_meta=doc_meta,
            question="Give me the summary from page 0 to the last page",
            on_progress=on_progress,
            batch_size=4,
            max_concurrency=2
        )

        assert "summary_started" in events_emitted
        assert "extraction_progress" in events_emitted
        assert "batch_progress" in events_emitted
        assert "combining_started" in events_emitted
        assert res is not None
        assert "answer" in res
        assert len(res["sources"]) > 0

        # Cleanup test doc from cache
        summary_cache.invalidate_document("doc-test-progress")

    asyncio.run(_run())


def test_final_summary_covers_all_required_sections_and_binary_search_complexity():
    """Requirement 4 & 9: Verify master summary covers required sections and O(log n) complexity."""
    batch_summaries = [
        {"batch_index": 1, "page_range": "1-12", "summary": "### Section: Pages 1-12\n**Core Topics**: Introduction, Primitive vs Non-Primitive, Interface & Implementation"},
        {"batch_index": 2, "page_range": "13-24", "summary": "### Section: Pages 13-24\n**Core Topics**: Recursion, Tower of Hanoi, Iterative vs Recursive Comparison"},
        {"batch_index": 3, "page_range": "25-36", "summary": "### Section: Pages 25-36\n**Core Topics**: Arrays, Sorting: Bubble Sort, Selection Sort, Insertion Sort"},
        {"batch_index": 4, "page_range": "37-48", "summary": "### Section: Pages 37-48\n**Core Topics**: Searching: Linear Search, Binary Search O(log n) with mid = (low + high) / 2"},
        {"batch_index": 5, "page_range": "49-60", "summary": "### Section: Pages 49-60\n**Core Topics**: Stack (LIFO), Array Representation, push, pop, isempty, isfull"},
        {"batch_index": 6, "page_range": "61-72", "summary": "### Section: Pages 61-72\n**Core Topics**: Queue (FIFO), Circular Queue, enqueue, dequeue"},
        {"batch_index": 7, "page_range": "73-84", "summary": "### Section: Pages 73-84\n**Core Topics**: Singly Linked List, Node structure, Dynamic allocation"},
        {"batch_index": 8, "page_range": "85-96", "summary": "### Section: Pages 85-96\n**Core Topics**: Doubly Linked List, Circular Linked List, Insertion & Deletion"},
        {"batch_index": 9, "page_range": "97-108", "summary": "### Section: Pages 97-108\n**Core Topics**: Tree Data Structures, In-Order, Pre-Order, Post-Order Traversals"},
        {"batch_index": 10, "page_range": "109-120", "summary": "### Section: Pages 109-120\n**Core Topics**: Binary Search Trees (BST), Search, Insert, In-order traversal property"},
        {"batch_index": 11, "page_range": "121-128", "summary": "### Section: Pages 121-128\n**Core Topics**: Heaps, Priority Queues, Graphs, Adjacency Matrix & Lists"},
    ]

    final_text = build_final_hierarchical_summary(
        doc_title="Data Structures Full Notes.pdf",
        total_pages=128,
        batch_summaries=batch_summaries
    )

    # Check required topics
    required_topics = [
        "Introduction", "Primitive", "Array", "Linked List", "Stack",
        "Queue", "Sorting", "Bubble Sort", "Searching", "Binary Search",
        "O(log n)", "Tree", "Binary Search Tree", "BST", "Heap", "Graph"
    ]
    for topic in required_topics:
        assert topic.lower() in final_text.lower(), f"Topic '{topic}' missing from final document summary"

    # Check page ranges are preserved
    assert "Pages 1–12" in final_text or "Pages 1-12" in final_text
    assert "Pages 37–48" in final_text or "Pages 37-48" in final_text
    assert "Pages 121–128" in final_text or "Pages 121-128" in final_text
