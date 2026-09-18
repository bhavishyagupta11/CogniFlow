"""
CogniFlow Explicit Query Concept Coverage Engine
Decomposes user queries into required conceptual requirements,
evaluates retrieved evidence passages against each concept independently,
and identifies covered vs. missing concepts to gate generation.
"""

import re
from typing import List, Dict, Any, Tuple, Set
from pydantic import BaseModel, Field


class ConceptCoverageResult(BaseModel):
    required_concepts: List[str] = Field(default_factory=list)
    covered_concepts: List[str] = Field(default_factory=list)
    missing_concepts: List[str] = Field(default_factory=list)
    concept_support: Dict[str, List[str]] = Field(default_factory=dict)  # concept -> list of chunk_ids
    distractor_chunk_ids: List[str] = Field(default_factory=list)
    coverage_ratio: float = 0.0
    status: str = "fully_answerable"  # fully_answerable | partially_answerable | not_answerable
    reason: str = ""

    @property
    def is_partial(self) -> bool:
        return self.status == "partially_answerable"

    @property
    def is_fully_answerable(self) -> bool:
        return self.status == "fully_answerable"

    def __getitem__(self, item):
        return getattr(self, item)



STOP_WORDS = {
    "what", "when", "where", "which", "how", "why", "who", "does", "did", "do",
    "explain", "compare", "the", "and", "for", "with", "from", "into", "onto",
    "uploaded", "document", "documents", "file", "files", "pdf", "tell", "show",
    "please", "list", "difference", "differences", "between", "them", "both", "all",
    "about", "describe", "give", "definition", "define", "overview", "detail",
    "details", "their", "b/w", "versus", "vs", "complete", "summary", "summay",
    "summarize", "entire", "whole", "full", "of", "this", "that", "these", "those",
    "is", "are", "was", "were", "there", "any", "some", "other", "another",
    "information", "info", "notes", "paper", "book", "text", "content", "read",
    "write", "provide", "can", "you", "could", "would", "should", "me", "find",
    "mention", "mentioned", "regard", "regarding"
}

# Distractor concepts in computer science notes that are frequently co-retrieved but unrelated
KNOWN_DISTRACTORS = {
    "linked list": ["linked list", "linked lists", "singly linked", "doubly linked", "head pointer", "node pointer"],
    "selection sort": ["selection sort", "selection-sort", "sorting algorithm", "unsorted subarray"],
    "bubble sort": ["bubble sort", "bubble-sort"],
    "insertion sort": ["insertion sort", "insertion-sort"],
    "tree": ["binary tree", "bst", "traversal", "inorder", "preorder"],
    "graph": ["adjacency matrix", "adjacency list", "dijkstra", "bfs", "dfs"]
}


def extract_required_concepts(query: str) -> List[str]:
    """
    Decomposes query into distinct technical concepts.
    Handles conjunctions ('and', 'or', 'vs', 'difference between X and Y').
    """
    cleaned = query.strip()
    
    # Check for comparative query: "difference between X and Y" or "difference b/w X and Y"
    diff_pattern = re.search(r"(?:difference(?:\s+b/w|\s+between)?)\s+([a-zA-Z0-9_\s-]+?)\s+(?:and|&|vs\.?)\s+([a-zA-Z0-9_\s-]+)", cleaned, re.IGNORECASE)
    if diff_pattern:
        c1 = diff_pattern.group(1).strip().lower()
        c2 = diff_pattern.group(2).strip().lower()
        # Clean filler words
        c1 = re.sub(r"^(?:an?\b|the\b|what\s+is(?:\s+an?)?\b)\s*", "", c1).strip()
        c2 = re.sub(r"^(?:an?\b|the\b|what\s+is(?:\s+an?)?\b)\s*", "", c2).split("?")[0].strip()
        concepts = []
        if c1 and len(c1) >= 2:
            concepts.append(c1)
        if c2 and len(c2) >= 2:
            concepts.append(c2)
        if "difference" not in concepts and "comparison" not in concepts:
            concepts.append("difference")
        return list(dict.fromkeys(concepts))

    # Pattern: "what is X and what is Y and what is the difference"
    multi_what = re.findall(r"(?:what\s+is|what\s+are|explain)\s+(?:(?:an?|the)\s+)?([a-zA-Z0-9_-]+)", cleaned, re.IGNORECASE)
    if len(multi_what) >= 2:
        res = [w.lower() for w in multi_what if w.lower() not in STOP_WORDS]
        if "difference" in cleaned.lower() or "b/w" in cleaned.lower() or "vs" in cleaned.lower():
            res.append("difference")
        if res:
            return list(dict.fromkeys(res))

    # General token-based extraction
    tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", cleaned)]
    meaningful = [t for t in tokens if t not in STOP_WORDS]
    
    if not meaningful:
        return [tokens[0]] if tokens else ["query"]

    # Combine multi-word technical concepts if known
    final_concepts = []
    i = 0
    while i < len(meaningful):
        if i + 1 < len(meaningful):
            pair = f"{meaningful[i]} {meaningful[i+1]}"
            if pair in [
                "linked list", "binary search", "search space", "time complexity",
                "data structure", "data structures", "binary tree", "heap sort"
            ]:
                final_concepts.append(pair)
                i += 2
                continue
        final_concepts.append(meaningful[i])
        i += 1

    return list(dict.fromkeys(final_concepts))


extract_query_concepts = extract_required_concepts


def analyze_concept_coverage(
    query: str,
    sources: List[Dict[str, Any]]
) -> ConceptCoverageResult:
    """
    Evaluates evidence chunks against each extracted concept.
    Detects which concepts are covered, which are absent, and detects distractor chunks.
    """
    required_concepts = extract_required_concepts(query)
    if not required_concepts:
        return ConceptCoverageResult(
            required_concepts=["general query"],
            covered_concepts=["general query"],
            missing_concepts=[],
            coverage_ratio=1.0,
            status="fully_answerable",
            reason="General query without specific discrete concept clusters."
        )

    concept_support: Dict[str, List[str]] = {c: [] for c in required_concepts}
    chunk_supported_concepts: Dict[str, Set[str]] = {}

    for s in sources:
        chunk_id = s.get("chunkId") or s.get("id") or s.get("chunk_id", "unknown-chunk")
        content = (s.get("chunkContent") or s.get("content") or s.get("text") or "").lower()
        title = (s.get("documentTitle") or s.get("title") or "").lower()
        full_text = f"{title} {content}"

        matched_for_this_chunk = set()
        for concept in required_concepts:
            if concept == "difference":
                if any(w in content for w in ["difference", "contrast", "versus", "vs", "compare", "whereas", "while"]):
                    concept_support[concept].append(chunk_id)
                    matched_for_this_chunk.add(concept)
            elif concept in ["data structure", "data structures"]:
                ds_terms = ["data structure", "data structures", "array", "arrays", "heap", "heaps", "tree", "trees", "list", "lists", "queue", "queues", "stack", "stacks", "graph", "graphs", "hash"]
                if any(re.search(rf"\b{re.escape(t)}\b", full_text) for t in ds_terms):
                    concept_support[concept].append(chunk_id)
                    matched_for_this_chunk.add(concept)
            else:
                pattern = rf"\b{re.escape(concept)}s?\b"
                if re.search(pattern, full_text):
                    concept_support[concept].append(chunk_id)
                    matched_for_this_chunk.add(concept)

        chunk_supported_concepts[chunk_id] = matched_for_this_chunk

    core_concepts = [c for c in required_concepts if c not in ["difference", "comparison"]]
    if not core_concepts:
        core_concepts = required_concepts

    covered_core = [c for c in core_concepts if len(concept_support[c]) > 0]
    missing_core = [c for c in core_concepts if len(concept_support[c]) == 0]

    # Check relational concept
    if "difference" in required_concepts:
        if len(covered_core) == len(core_concepts) and len(concept_support.get("difference", [])) > 0:
            covered_concepts = covered_core + ["difference"]
            missing_concepts = []
        else:
            covered_concepts = covered_core
            missing_concepts = missing_core + (["difference"] if "difference" in required_concepts else [])
    else:
        covered_concepts = covered_core
        missing_concepts = missing_core

    coverage_ratio = len(covered_concepts) / max(len(required_concepts), 1)

    # Detect distractor chunks: chunks that discuss unrequested distractor topics (e.g. selection sort, linked list)
    # when cleaner dedicated chunks exist for the actual covered concepts.
    distractor_chunk_ids = []
    for s in sources:
        cid = s.get("chunkId") or s.get("id") or s.get("chunk_id", "unknown-chunk")
        content = (s.get("chunkContent") or s.get("content") or s.get("text") or "").lower()
        title = (s.get("documentTitle") or s.get("title") or "").lower()
        full_text = f"{title} {content}"
        supported_by_cid = chunk_supported_concepts.get(cid, set())

        for dist_name, patterns in KNOWN_DISTRACTORS.items():
            # If the user asked about heaps, trees are intrinsically related (heaps are complete binary trees)
            if dist_name == "tree" and any(k in required_concepts for k in ["heap", "heaps", "priority queue", "priority queues"]):
                continue

            if dist_name not in required_concepts:
                matched_dist = [p for p in patterns if p in full_text]
                if matched_dist:
                    # If this chunk directly supports required query concepts, only mark as distractor
                    # if cleaner chunks exist that support ALL the same concepts without the distractor
                    if supported_by_cid:
                        cleaner_chunks = [
                            cs for cs in sources
                            if (cs.get("chunkId") or cs.get("id") or cs.get("chunk_id")) != cid
                            and supported_by_cid.issubset(chunk_supported_concepts.get(cs.get("chunkId") or cs.get("id") or cs.get("chunk_id"), set()))
                            and not any(p in (cs.get("content") or cs.get("chunkContent") or "").lower() for p in patterns)
                        ]
                        if cleaner_chunks:
                            distractor_chunk_ids.append(cid)
                            break
                    else:
                        # Chunk does not support any required concepts and contains distractor patterns
                        distractor_chunk_ids.append(cid)
                        break


    if len(missing_concepts) == 0:
        status = "fully_answerable"
        reason = f"Full evidence coverage across all requested concepts: {', '.join(covered_concepts)}."
    elif len(covered_concepts) > 0:
        status = "partially_answerable"
        reason = (
            f"Corpus contains evidence for '{', '.join(covered_concepts)}', "
            f"but lacks sufficient evidence for '{', '.join(missing_concepts)}'."
        )
    else:
        status = "not_answerable"
        reason = f"Selected corpus does not contain evidence for: {', '.join(missing_concepts)}."

    return ConceptCoverageResult(
        required_concepts=required_concepts,
        covered_concepts=covered_concepts,
        missing_concepts=missing_concepts,
        concept_support=concept_support,
        distractor_chunk_ids=distractor_chunk_ids,
        coverage_ratio=round(coverage_ratio, 2),
        status=status,
        reason=reason
    )
