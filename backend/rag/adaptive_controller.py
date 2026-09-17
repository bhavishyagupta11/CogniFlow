"""
CogniFlow Adaptive Controller & Execution Strategy Selector
Implements Pre-Execution Correction 7 & Specification Sections 7 & 8:
- Decouples USER MODE (FAST, ADAPTIVE RAG, DEEP RESEARCH, GENERAL CHAT) from EXECUTION COMPLEXITY.
- For ADAPTIVE RAG, evaluates:
  1. Query complexity, multi-concept signals, and comparison requirements
  2. Empirical retrieval score distribution (top score, score gap, candidate agreement)
  3. Dynamic classification into internal: SIMPLE, MODERATE, or COMPLEX
- Strictly obeys Pre-Execution Correction 2: Uses configurable thresholds from backend/config.py
  calibrated against empirical retrieval score distributions.
"""

from typing import List, Dict, Any, Tuple
import re

from backend.config import (
    ADAPTIVE_SIMPLE_THRESHOLD,
    ADAPTIVE_SCORE_GAP_THRESHOLD,
    RERANK_SCORE_THRESHOLD,
    RERANK_ENABLED,
    VERIFICATION_ENABLED
)


def analyze_query_characteristics(query: str) -> Dict[str, Any]:
    """Analyzes linguistic and structural complexity of the query."""
    q_clean = query.strip()
    words = re.findall(r"\b\w+\b", q_clean)
    word_count = len(words)

    # Comparison and multi-hop indicators
    comp_patterns = [
        r"\bcompare\b", r"\bcontrast\b", r"\bdifference\b", r"\bdifferences\b",
        r"\bversus\b", r"\bvs\.?\b", r"\btradeoffs?\b", r"\bbetter than\b",
        r"\badvantages and disadvantages\b", r"\bpros and cons\b"
    ]
    is_comparison = any(re.search(p, q_clean, re.IGNORECASE) for p in comp_patterns)

    # Multi-part / multi-concept indicators
    multi_part = bool(re.search(r"\band\b.*\balso\b|\bfirst\b.*\bthen\b|\bboth\b.*\band\b", q_clean, re.IGNORECASE))
    has_multiple_questions = q_clean.count("?") > 1

    return {
        "word_count": word_count,
        "is_comparison": is_comparison,
        "is_multipart": multi_part or has_multiple_questions,
        "is_long_analytical": word_count > 25
    }


def evaluate_retrieval_distribution(
    candidates: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Computes empirical distribution statistics from retrieved candidates:
    - top_score: highest candidate retrieval score
    - score_gap: gap between 1st and 2nd candidate
    - score_spread: gap between 1st and Nth candidate
    - candidate_count: number of retrieved evidence candidates
    """
    if not candidates:
        return {
            "top_score": 0.0,
            "second_score": 0.0,
            "score_gap": 0.0,
            "score_spread": 0.0,
            "candidate_count": 0,
            "has_decisive_leader": False
        }

    scores = [float(c.get("score", 0.5)) for c in candidates]
    top_score = scores[0]
    second_score = scores[1] if len(scores) > 1 else top_score
    last_score = scores[-1]

    score_gap = round(top_score - second_score, 4)
    score_spread = round(top_score - last_score, 4)

    has_decisive_leader = (
        top_score >= ADAPTIVE_SIMPLE_THRESHOLD and
        score_gap >= ADAPTIVE_SCORE_GAP_THRESHOLD
    )

    return {
        "top_score": top_score,
        "second_score": second_score,
        "score_gap": score_gap,
        "score_spread": score_spread,
        "candidate_count": len(candidates),
        "has_decisive_leader": has_decisive_leader
    }


class AdaptiveController:
    """
    Determines execution path and component activation based on
    User Mode + Query Linguistics + Retrieval Score Distribution.
    """

    @staticmethod
    def select_execution_strategy(
        user_mode: str,
        query: str,
        initial_candidates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Returns execution decision dictionary:
        {
            "user_mode": str,
            "complexity": "simple" | "moderate" | "complex" | "fast" | "deep_research" | "general_chat",
            "needs_reranking": bool,
            "needs_parallel_retrieval": bool,
            "needs_verification": bool,
            "reason": str,
            "metrics": Dict[str, Any]
        }
        """
        mode_normalized = (user_mode or "adaptive_rag").lower().strip()
        q_analysis = analyze_query_characteristics(query)
        dist_analysis = evaluate_retrieval_distribution(initial_candidates)

        # ─────────────────────────────────────────────────────────────
        # 1. USER MODE OVERRIDE (Explicit User Intent is Paramount)
        # ─────────────────────────────────────────────────────────────
        if mode_normalized == "general_chat":
            return {
                "user_mode": "general_chat",
                "complexity": "general_chat",
                "needs_retrieval": False,
                "needs_reranking": False,
                "needs_parallel_retrieval": False,
                "needs_verification": False,
                "reason": "General Chat mode active: direct LLM interaction without document retrieval or citations.",
                "metrics": {"query_analysis": q_analysis}
            }

        if mode_normalized == "fast":
            # Fast Mode: minimal path, single generation call, conditional light rerank only if ambiguous
            needs_rerank = RERANK_ENABLED and (not dist_analysis["has_decisive_leader"]) and (dist_analysis["candidate_count"] > 2)
            return {
                "user_mode": "fast",
                "complexity": "fast",
                "needs_retrieval": True,
                "needs_reranking": needs_rerank,
                "needs_parallel_retrieval": False,
                "needs_verification": False,
                "reason": "Fast mode selected: sub-3s targeted execution with single generation call and deterministic citations.",
                "metrics": {"query_analysis": q_analysis, "retrieval_distribution": dist_analysis}
            }

        if mode_normalized == "deep_research":
            # Deep Research: multi-agent orchestration, parallel retrieval workers, synthesis, verifier
            return {
                "user_mode": "deep_research",
                "complexity": "deep_research",
                "needs_retrieval": True,
                "needs_reranking": True,
                "needs_parallel_retrieval": True,
                "needs_verification": VERIFICATION_ENABLED,
                "reason": "Deep Research mode selected: multi-stage evidence synthesis with bounded parallel retrieval.",
                "metrics": {"query_analysis": q_analysis, "retrieval_distribution": dist_analysis}
            }

        # ─────────────────────────────────────────────────────────────
        # 2. ADAPTIVE RAG (Default Mode: dynamic SIMPLE / MODERATE / COMPLEX)
        # ─────────────────────────────────────────────────────────────
        # Complex Trigger: multi-hop comparisons, long analytical prompts, or weak evidence
        if q_analysis["is_comparison"] or q_analysis["is_multipart"] or q_analysis["is_long_analytical"]:
            return {
                "user_mode": "adaptive_rag",
                "complexity": "complex",
                "needs_retrieval": True,
                "needs_reranking": True,
                "needs_parallel_retrieval": True,
                "needs_verification": VERIFICATION_ENABLED,
                "reason": f"Adaptive RAG classified as COMPLEX: {'comparative query' if q_analysis['is_comparison'] else 'multi-part reasoning'}.",
                "metrics": {"query_analysis": q_analysis, "retrieval_distribution": dist_analysis}
            }

        # Simple Trigger: high-confidence retrieval with decisive top candidate
        if dist_analysis["has_decisive_leader"] and q_analysis["word_count"] <= 18:
            return {
                "user_mode": "adaptive_rag",
                "complexity": "simple",
                "needs_retrieval": True,
                "needs_reranking": False,
                "needs_parallel_retrieval": False,
                "needs_verification": False,
                "reason": f"Adaptive RAG classified as SIMPLE: decisive top candidate (score={dist_analysis['top_score']}, gap={dist_analysis['score_gap']}).",
                "metrics": {"query_analysis": q_analysis, "retrieval_distribution": dist_analysis}
            }

        # Moderate Trigger: ambiguous scores or intermediate query length
        needs_rerank = RERANK_ENABLED and (dist_analysis["candidate_count"] > 2)
        return {
            "user_mode": "adaptive_rag",
            "complexity": "moderate",
            "needs_retrieval": True,
            "needs_reranking": needs_rerank,
            "needs_parallel_retrieval": False,
            "needs_verification": False,
            "reason": f"Adaptive RAG classified as MODERATE: candidates requiring conditional reranking (gap={dist_analysis['score_gap']}).",
            "metrics": {"query_analysis": q_analysis, "retrieval_distribution": dist_analysis}
        }


adaptive_controller = AdaptiveController()
