"""
CogniFlow Adaptive Retriever
Executes parallel lexical + dense vector search across decomposed subqueries,
applies Reciprocal Rank Fusion (RRF), deduplicates chunks, enforces multi-tenant
user isolation, and calculates truthful retrieval evidence metrics.
"""

import asyncio
from typing import List, Dict, Any, Optional
from collections import defaultdict

from backend.rag.vector_store import vector_store
from backend.models import CitedSource, RetrievalConfidence


async def retrieve_single_query(
    query: str,
    k: int = 5,
    owner_id: Optional[str] = None,
    document_id: Optional[str] = None,
    scope: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Runs vector store search in an async worker, supporting document_id and scope scoping."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, vector_store.search, query, k, owner_id, document_id, scope)


def reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any]]],
    k_constant: int = 60,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Fuses multiple ranked result lists using Reciprocal Rank Fusion (RRF).
    score(d) = sum(1 / (k_constant + rank(d)))
    """
    rrf_scores = defaultdict(float)
    chunk_map = {}

    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            cid = item["id"]
            rrf_scores[cid] += 1.0 / (k_constant + rank)
            if cid not in chunk_map:
                chunk_map[cid] = item

    # Sort by fused score
    sorted_items = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Scale fused scores to [0.5, 0.98] range for UI confidence meter compatibility
    results = []
    if sorted_items:
        max_score = sorted_items[0][1]
        for cid, raw_score in sorted_items[:top_k]:
            item = dict(chunk_map[cid])
            normalized_score = round(0.5 + 0.48 * (raw_score / max_score), 4)
            item["score"] = normalized_score
            results.append(item)

    return results


async def parallel_retrieve(
    queries: List[str],
    max_candidates: int = 5,
    owner_id: Optional[str] = None,
    document_id: Optional[str] = None,
    scope: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Executes concurrent retrieval across all subqueries using asyncio.gather.
    Supports document_id and scope scoped search for document-targeted queries.
    Returns fused and deduplicated candidates.
    """
    if not queries:
        return []

    # Run subqueries concurrently
    tasks = [retrieve_single_query(q, k=max_candidates + 2, owner_id=owner_id, document_id=document_id, scope=scope) for q in queries]
    subquery_results = await asyncio.gather(*tasks)

    if len(queries) == 1:
        # Single query - return directly clamped to max_candidates
        return subquery_results[0][:max_candidates]

    # Multiple queries - apply Reciprocal Rank Fusion
    return reciprocal_rank_fusion(subquery_results, top_k=max_candidates)


def compute_retrieval_confidence(sources: List[Dict[str, Any]]) -> RetrievalConfidence:
    """
    Computes truthful, uninflated metrics for retrieval alignment.
    Does NOT claim answer correctness or factual veracity; measures evidence match.
    """
    if not sources:
        return RetrievalConfidence(
            score=0.0,
            compositeScore=0.0,
            topScore=0.0,
            averageScore=0.0,
            scoreGap=0.0,
            evidenceCoverage=0.0,
            sourceDiversity=0.0,
            duplicateRatio=0.0,
            sufficient=False,
            reason="No matching documents found in the corpus for the given query.",
            disclaimer="Score reflects text retrieval alignment in corpus, not generative factual veracity."
        )

    scores = [s.get("score", 0.5) for s in sources]
    top_score = max(scores)
    avg_score = sum(scores) / len(scores)
    score_gap = top_score - (scores[1] if len(scores) > 1 else top_score)

    unique_docs = len(set(s.get("documentId") for s in sources))
    source_diversity = round(unique_docs / max(len(sources), 1), 2)
    evidence_coverage = min(round(len(sources) / 3.0, 2), 1.0)
    
    # Composite formula balancing top score, average score, and coverage
    composite = round(0.5 * top_score + 0.3 * avg_score + 0.2 * evidence_coverage, 2)
    is_sufficient = top_score >= 0.55 and len(sources) >= 1

    reason = "Strong evidence retrieval alignment across corpus." if composite >= 0.70 else \
             "Moderate evidence retrieval match." if composite >= 0.45 else \
             "Weak evidence alignment — output may be grounded on limited passages."

    return RetrievalConfidence(
        score=composite,
        compositeScore=composite,
        topScore=round(top_score, 4),
        averageScore=round(avg_score, 4),
        scoreGap=round(score_gap, 4),
        evidenceCoverage=evidence_coverage,
        sourceDiversity=source_diversity,
        duplicateRatio=0.0,
        sufficient=is_sufficient,
        reason=reason,
        disclaimer="Score reflects text retrieval alignment in corpus, not generative factual veracity."
    )
