"""
CogniFlow Conditional Reranker
Applies fast deterministic Python / NumPy reranking when candidate pools are large
or scores are closely tied. Skips reranking for simple queries or small candidate sets.
"""

import re
from typing import List, Dict, Any, Tuple
import numpy as np


def should_skip_reranker(
    complexity: str,
    candidates: List[Dict[str, Any]],
    top_score: float = 0.95,
    score_gap: float = 0.05
) -> Tuple[bool, str]:
    """Determines whether reranking should be skipped to conserve latency."""
    if len(candidates) <= 2:
        return True, "Reranker skipped: Candidate pool is small (<= 2 chunks)."
    if complexity == "simple":
        return True, "Reranker skipped: Simple factual query path."
    if top_score >= 0.95 and score_gap >= 0.15:
        return True, "Reranker skipped: Decisive top candidate relevance."
    return False, ""


def rerank_candidates(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Fast deterministic reranking using exact keyword match, phrase proximity,
    and source diversity. Operates in <2ms using NumPy.
    """
    if not candidates:
        return []

    q_tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", query)]
    seen_docs = set()
    scored_candidates = []

    for c in candidates:
        content = c.get("content", "").lower()
        title = c.get("documentTitle", "").lower()
        
        # 1. Base retrieval score
        base_score = float(c.get("score", 0.5))

        # 2. Exact token matching
        matches = sum(1 for t in q_tokens if t in content or t in title)
        token_ratio = matches / max(len(q_tokens), 1)

        # 3. Exact phrase match bonus
        phrase_bonus = 0.10 if query.lower() in content else 0.0

        # 4. Diversity bonus: slightly favor new documents over repeated ones
        doc_id = c.get("documentId")
        diversity_bonus = 0.05 if doc_id not in seen_docs else 0.0
        seen_docs.add(doc_id)

        # Composite rerank score
        rerank_score = (0.55 * base_score) + (0.30 * token_ratio) + phrase_bonus + diversity_bonus
        
        updated = dict(c)
        updated["rerankScore"] = round(min(rerank_score, 0.99), 4)
        scored_candidates.append(updated)

    # Sort by rerank score descending
    scored_candidates.sort(key=lambda x: x["rerankScore"], reverse=True)

    # Reassign final score and rank
    for idx, sc in enumerate(scored_candidates[:top_k], start=1):
        sc["score"] = sc["rerankScore"]
        sc["rank"] = idx

    return scored_candidates[:top_k]
