"""
CogniFlow Deterministic Query Complexity Classifier
Fast, zero-latency, rule-based classification into:
- simple: Factual lookups, parameter counts, direct definitions (Sub-3s path)
- standard: Architectural explanations, mechanism overviews (Conditional rerank, lightweight verify)
- complex: Cross-document comparisons, multi-part, multi-hop (Parallel subqueries, full fusion)
- high_risk: Ambiguous, contradictory, out-of-domain (Deep verification, strict evidence threshold)
"""

import re
from typing import List
from backend.models import QueryComplexityDecision


def extract_subqueries(question: str) -> List[str]:
    """Decomposes a complex comparison or multi-part query into 2-3 focused subqueries."""
    q_clean = question.strip()
    
    # Check for "compare X and Y"
    compare_match = re.search(r"(?:compare|contrast|difference between)\s+([^,]+?)\s+(?:and|with|versus|vs\.?)\s+(.+)", q_clean, re.IGNORECASE)
    if compare_match:
        term_a = compare_match.group(1).strip()
        term_b = compare_match.group(2).strip()
        # Remove trailing punctuation
        term_b = re.sub(r"[?.!]+$", "", term_b).strip()
        return [
            f"{term_a} architecture and technical characteristics",
            f"{term_b} architecture and technical characteristics",
        ]
        
    # Check for multi-clause questions separated by "and how" or ";"
    clauses = re.split(r";|\band\s+(?:how|what|why|when)\b", q_clean, flags=re.IGNORECASE)
    if len(clauses) >= 2:
        results = [c.strip() for c in clauses if len(c.strip()) > 8]
        if len(results) >= 2:
            return results[:3]
            
    return [q_clean]


def classify_query(question: str, mode: str = "deep_research") -> QueryComplexityDecision:
    """
    Deterministically evaluates query complexity with zero LLM latency (<1ms).
    Returns a typed QueryComplexityDecision guiding downstream pipeline policies.
    """
    if not question or not question.strip():
        return QueryComplexityDecision(
            complexity="simple",
            needs_query_rewrite=False,
            needs_decomposition=False,
            needs_reranking=False,
            needs_critic=False,
            max_candidates=2,
            max_subqueries=1,
            time_budget_ms=2000,
            reason="Empty or trivial query fallback"
        )

    q = question.lower().strip()
    words = re.findall(r"\b[a-zA-Z0-9_-]+\b", q)
    num_words = len(words)

    # 0. Full-Document Summary Intent Signals (Requirement 1 & 2)
    summary_intent_patterns = [
        r"\bcomplete\s+summary\b",
        r"\bentire\s+document\b",
        r"\bwhole\s+document\b",
        r"\bentire\s+pdf\b",
        r"\bwhole\s+pdf\b",
        r"\bfrom\s+(?:the\s+)?(?:first|0|page\s*0)\s+(?:page\s+)?to\s+(?:the\s+)?last\s+page\b",
        r"\bfrom\s+page\s+0\s+to\s+(?:the\s+)?last\s+page\b",
        r"\bpage\s+0\s+to\s+(?:the\s+)?last\s+page\b",
        r"\b0\s+to\s+(?:the\s+)?last\s+page\b",
        r"\bsummarize\s+all\s+pages\b",
        r"\bsummary\s+(?:from|of)\s+all\s+pages\b",
        r"\bsummary\s+from\s+page\b",
        r"\bnothing\s+should\s+be\s+missed\b",
        r"\bchapter[- ]?wise\s+summary\b",
        r"\bfull\s+pdf\s+summary\b",
        r"\bfull\s+document\s+summary\b",
        r"\bsummarize\s+(?:the\s+)?(?:entire|whole|all)\b",
        r"\bcomprehensive\s+(?:document\s+)?summary\b",
        r"\bsummarize\s+from\s+(?:page\s+0|first\s+page)\b",
    ]
    if any(re.search(pat, q, re.IGNORECASE) for pat in summary_intent_patterns):
        return QueryComplexityDecision(
            complexity="document_summary",
            needs_query_rewrite=False,
            needs_decomposition=False,
            needs_reranking=False,
            needs_critic=False,
            max_candidates=1000,
            max_subqueries=1,
            time_budget_ms=60000,
            reason="Full-document hierarchical summarization detected"
        )
    out_of_domain_indicators = [
        "recipe", "weather", "horoscope", "stock price", "celebrity", "flight", "hotel"
    ]
    if any(k in q for k in out_of_domain_indicators):
        return QueryComplexityDecision(
            complexity="high_risk",
            needs_query_rewrite=False,
            needs_decomposition=False,
            needs_reranking=False,
            needs_critic=True,
            max_candidates=3,
            max_subqueries=1,
            time_budget_ms=3000,
            reason="Query touches out-of-domain concepts requiring strict evidence bounding"
        )

    # 2. Complex Signals (Comparison, Multi-Hop, Multi-Part)
    comparison_signals = [
        "compare", "versus", " vs ", " vs. ", "difference between",
        "trade-off", "tradeoff", "advantages and disadvantages",
        "pros and cons", "contrast"
    ]
    multi_part_signals = [
        "?", ";", "additionally", "furthermore", "as well as", "influence"
    ]
    is_comparison = any(s in q for s in comparison_signals)
    has_multiple_questions = q.count("?") > 1

    if is_comparison or has_multiple_questions or num_words >= 20:
        return QueryComplexityDecision(
            complexity="complex",
            needs_query_rewrite=True,
            needs_decomposition=True,
            needs_reranking=True,
            needs_critic=True,
            max_candidates=8,
            max_subqueries=3,
            time_budget_ms=10000,
            reason="Multi-entity comparison or multi-hop inquiry requiring subquery decomposition"
        )

    # 3. Simple Signals (Specific facts, definitions, parameter counts)
    simple_definition_signals = [
        "what is ", "what are ", "define ", "definition of ", "who wrote ",
        "who created ", "who proposed ", "author of ", "year of "
    ]
    simple_fact_signals = [
        "how many parameters", "parameter count", "benchmark score",
        "context window", "hidden size", "number of layers"
    ]

    # Check for document inventory/project list queries first
    inventory_signals = [
        "which are the projects", "what projects", "list all projects", "list the projects",
        "which projects", "inventory", "all projects", "what are the projects", "projects in",
        "projects mentioned", "projects described", "projects are in"
    ]
    if any(s in q for s in inventory_signals):
        return QueryComplexityDecision(
            complexity="document_list_extraction",
            needs_query_rewrite=False,
            needs_decomposition=False,
            needs_reranking=False,
            needs_critic=False,
            max_candidates=10,
            max_subqueries=1,
            time_budget_ms=6000,
            reason="Document inventory and project listing query requiring adaptive multi-chunk coverage"
        )

    is_simple_def = any(q.startswith(s) or s in q for s in simple_definition_signals)
    is_simple_fact = any(s in q for s in simple_fact_signals)

    if (is_simple_def or is_simple_fact) and num_words <= 12:
        return QueryComplexityDecision(
            complexity="simple",
            needs_query_rewrite=False,
            needs_decomposition=False,
            needs_reranking=False,
            needs_critic=False,
            max_candidates=3,
            max_subqueries=1,
            time_budget_ms=3000,
            reason="Direct factual or definitional lookup eligible for sub-3s fast path"
        )

    # 4. Standard Technical Questions (Architectural explanations, mechanisms)
    return QueryComplexityDecision(
        complexity="standard",
        needs_query_rewrite=False,
        needs_decomposition=False,
        needs_reranking=True,
        needs_critic=False,
        max_candidates=5,
        max_subqueries=1,
        time_budget_ms=6000,
        reason="Technical architectural explanation with conditional reranking"
    )
