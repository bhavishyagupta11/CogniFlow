"""
CogniFlow Heuristic Rescorer (Deterministic Lexical-Diversity Rescorer)
Applies fast deterministic Python / NumPy heuristic rescoring when candidate pools
are ambiguous or scores are closely tied. Skips rescoring for simple queries or small candidate sets.

ARCHITECTURE NOTE:
This component is a HEURISTIC RESCORER (deterministic scoring formula),
NOT an LLM reranker and NOT a neural cross-encoder.
Formula: 0.55 * base_score + 0.30 * token_ratio + 0.10 * phrase_match + 0.05 * diversity_bonus
"""

import re
from typing import List, Dict, Any, Tuple, Optional
import numpy as np


from backend.config import (
    RERANK_ENABLED,
    ADAPTIVE_SIMPLE_THRESHOLD,
    ADAPTIVE_SCORE_GAP_THRESHOLD,
    RERANK_SCORE_THRESHOLD
)


def should_skip_reranker(
    mode: str,
    complexity: str,
    candidates: List[Dict[str, Any]],
    top_score: Optional[float] = None,
    score_gap: Optional[float] = None
) -> Tuple[bool, str]:
    """
    Authoritative Invocation Policy for HEURISTIC RESCORER:
    - GENERAL_CHAT: never
    - DOCUMENT_SUMMARY: never (summary uses full document / cache)
    - FAST: conditional only when retrieval ambiguity requires it
    - ADAPTIVE_RAG: run for >= 3 meaningful candidates
    - DEEP_RESEARCH: run for >= 2 candidates
    """
    norm_mode = (mode or "").lower().strip()
    norm_comp = (complexity or "").lower().strip()

    if norm_mode == "general_chat" or norm_comp == "general_chat":
        return True, "Heuristic Rescorer skipped: General chat does not use document retrieval."

    if norm_comp == "document_summary":
        return True, "Heuristic Rescorer skipped: Document summary operates at document/section scope."

    if not RERANK_ENABLED:
        return True, "Heuristic Rescorer disabled in system configuration."

    cand_len = len(candidates) if candidates else 0
    if cand_len == 0:
        return True, "Heuristic Rescorer skipped: Zero candidate chunks."

    if norm_mode == "deep_research":
        if cand_len < 2:
            return True, "Heuristic Rescorer skipped: Deep research candidate pool < 2."
        return False, ""

    if norm_mode == "fast" or norm_comp == "fast":
        if cand_len < 3:
            return True, "Heuristic Rescorer skipped: Fast mode requires >= 3 candidates for rescoring."
        s_top = top_score if top_score is not None else (float(candidates[0].get("score", 0.5)) if candidates else 0.0)
        s_second = float(candidates[1].get("score", s_top)) if len(candidates) > 1 else s_top
        s_gap = score_gap if score_gap is not None else (s_top - s_second)
        # Fast mode: only invoke when top candidate score is ambiguous or gap is tight
        if s_top >= 0.70 and s_gap >= 0.08:
            return True, f"Heuristic Rescorer skipped: Decisive top candidate relevance in Fast mode (score {s_top:.2f}, gap {s_gap:.2f})."
        return False, ""

    # ADAPTIVE_RAG (default)
    if cand_len < 3:
        return True, f"Heuristic Rescorer skipped: Candidate pool is small ({cand_len} < 3 chunks)."

    return False, ""


def rerank_candidates(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    HEURISTIC RESCORER:
    Fast deterministic heuristic scoring using exact token ratio, phrase match,
    and document diversity bonus. Operates in <1.5ms using pure Python/NumPy.
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

        # Composite heuristic rescore
        rerank_score = (0.55 * base_score) + (0.30 * token_ratio) + phrase_bonus + diversity_bonus
        
        updated = dict(c)
        updated["rerankScore"] = round(min(rerank_score, 0.99), 4)
        updated["rescoreFormula"] = "0.55*base + 0.30*token_ratio + phrase + diversity"
        scored_candidates.append(updated)

    # Sort by rerank score descending
    scored_candidates.sort(key=lambda x: x["rerankScore"], reverse=True)

    # Reassign final score and rank
    for idx, sc in enumerate(scored_candidates[:top_k], start=1):
        sc["score"] = sc["rerankScore"]
        sc["rank"] = idx

    return scored_candidates[:top_k]


def evaluate_heuristic_rescorer_impact(
    before_candidates: List[Dict[str, Any]],
    after_candidates: List[Dict[str, Any]],
    duration_ms: int = 0,
    invoked: bool = True
) -> Dict[str, Any]:
    """
    Measures before/after ranking quality to provide authoritative telemetry:
    - candidate_count
    - rerank_invoked
    - rerank_type ("HEURISTIC RESCORER")
    - before_top_ids
    - after_top_ids
    - top1_changed
    - top_k_changed
    - duration_ms
    """
    before_ids = [c.get("id") or c.get("chunk_id") or c.get("chunkId") for c in (before_candidates or [])]
    after_ids = [c.get("id") or c.get("chunk_id") or c.get("chunkId") for c in (after_candidates or [])]

    cand_cnt = len(before_candidates) if before_candidates else len(after_candidates) if after_candidates else 0
    top_1_changed = (before_ids[0] != after_ids[0]) if (before_ids and after_ids) else False
    top_k_changed = before_ids != after_ids if (before_ids and after_ids) else False

    matches = 0
    min_len = min(len(before_ids), len(after_ids))
    for i in range(min_len):
        if before_ids[i] == after_ids[i]:
            matches += 1
    reorder_rate = round(1.0 - (matches / max(min_len, 1)), 3) if min_len > 0 else 0.0

    return {
        "candidate_count": cand_cnt,
        "rerank_invoked": invoked,
        "rerank_type": "HEURISTIC RESCORER",
        "before_top_ids": before_ids[:5],
        "after_top_ids": after_ids[:5],
        "top1_changed": top_1_changed,
        "top_k_changed": top_k_changed,
        "reorder_rate": reorder_rate,
        "duration_ms": duration_ms
    }
