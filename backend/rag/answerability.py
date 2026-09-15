"""
CogniFlow 4-State Answerability & Heuristic Contradiction Gate
Determines if retrieved evidence is sufficient to ground an answer:
- fully_answerable: Full term & context coverage in evidence
- partially_answerable: Incomplete evidence; missing information identified
- not_answerable: Zero relevant grounding in knowledge base
- contradictory: Opposing assertions identified across retrieved passages
"""

import re
from typing import List, Dict, Any
from backend.models import AnswerabilityResult


OPPOSING_PAIRS = [
    (r"\buses\b", r"\bdoes not use\b|\bnever uses\b"),
    (r"\bsuperior\b|\boutperforms\b", r"\binferior\b|\bunderperforms\b"),
    (r"\brequires\b", r"\bdoes not require\b|\boptional\b"),
    (r"\bincreased\b|\bhigher\b", r"\bdecreased\b|\blower\b"),
    (r"\benabled\b", r"\bdisabled\b"),
    (r"\bsuccess\b", r"\bfailure\b"),
]


def detect_answerability(
    question: str,
    sources: List[Dict[str, Any]]
) -> AnswerabilityResult:
    """
    Evaluates grounding sufficiency and flags contradictions using clearly labeled
    heuristic safeguards. Does NOT claim universal contradiction detection.
    """
    if not sources:
        return AnswerabilityResult(
            status="not_answerable",
            answerable=False,
            confidence=0.10,
            supportingChunkIds=[],
            missingInformation=["Zero candidate chunks retrieved for this question."],
            conflictingChunkIds=[],
            reason="Zero candidate chunks retrieved for this question."
        )

    q_tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", question)]
    # Filter common stop words and conversational query meta-terms
    stop_words = {
        "what", "when", "where", "which", "how", "does", "explain", "compare", "the", "and", "for", "with",
        "uploaded", "document", "documents", "file", "files", "pdf", "tell", "show", "please", "list"
    }
    key_tokens = [t for t in q_tokens if t not in stop_words]

    if not key_tokens:
        key_tokens = q_tokens

    corpus_text = " ".join([s.get("chunkContent", s.get("content", "")) + " " + s.get("documentTitle", "") for s in sources]).lower()

    # 1. Contradiction Detection across chunks
    if len(sources) >= 2:
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                c1_text = sources[i].get("chunkContent", sources[i].get("content", "")).lower()
                c2_text = sources[j].get("chunkContent", sources[j].get("content", "")).lower()

                for pos_pattern, neg_pattern in OPPOSING_PAIRS:
                    has_pos_1 = bool(re.search(pos_pattern, c1_text))
                    has_neg_2 = bool(re.search(neg_pattern, c2_text))
                    has_pos_2 = bool(re.search(pos_pattern, c2_text))
                    has_neg_1 = bool(re.search(neg_pattern, c1_text))

                    if (has_pos_1 and has_neg_2) or (has_pos_2 and has_neg_1):
                        # Verify that both chunks mention at least one common query subject
                        shared_subjects = [t for t in key_tokens if t in c1_text and t in c2_text]
                        if shared_subjects:
                            id_i = sources[i].get("chunkId", sources[i].get("id", f"chunk-{i}"))
                            id_j = sources[j].get("chunkId", sources[j].get("id", f"chunk-{j}"))
                            return AnswerabilityResult(
                                status="contradictory",
                                answerable=True,
                                confidence=0.75,
                                supportingChunkIds=[id_i, id_j],
                                missingInformation=[],
                                conflictingChunkIds=[id_i, id_j],
                                reason=f"Heuristic contradiction detected regarding '{shared_subjects[0]}' between retrieved passages."
                            )

    # 2. Coverage calculation
    matched_tokens = [t for t in key_tokens if t in corpus_text]
    coverage = len(matched_tokens) / max(len(key_tokens), 1)

    supporting_ids = [
        s.get("chunkId", s.get("id", ""))
        for s in sources
        if any(t in s.get("chunkContent", s.get("content", "")).lower() for t in matched_tokens)
    ]
    if not supporting_ids:
        supporting_ids = [s.get("chunkId", s.get("id", "")) for s in sources]

    if coverage >= 0.70:
        return AnswerabilityResult(
            status="fully_answerable",
            answerable=True,
            confidence=round(0.85 + (coverage * 0.14), 2),
            supportingChunkIds=supporting_ids,
            missingInformation=[],
            conflictingChunkIds=[],
            reason="High key-term overlap and factual support present in retrieved chunks."
        )

    if coverage >= 0.35:
        missing = [t for t in key_tokens if t not in matched_tokens]
        return AnswerabilityResult(
            status="partially_answerable",
            answerable=True,
            confidence=round(0.50 + (coverage * 0.30), 2),
            supportingChunkIds=supporting_ids,
            missingInformation=missing[:5] if missing else ["Partial context available"],
            conflictingChunkIds=[],
            reason=f"Corpus provides partial context but lacks coverage for: {', '.join(missing[:3]) if missing else 'query aspects'}."
        )

    missing = [t for t in key_tokens if t not in matched_tokens]
    return AnswerabilityResult(
        status="not_answerable",
        answerable=False,
        confidence=0.25,
        supportingChunkIds=[],
        missingInformation=missing[:5] if missing else ["Query terms are absent from the indexed literature."],
        conflictingChunkIds=[],
        reason="Query terms are absent from the indexed literature."
    )


def check_document_summary_answerability(
    target_doc_id: Any,
    target_filename: Any,
    doc_exists: bool,
    page_count: int,
    processing_status: str = "completed"
) -> AnswerabilityResult:
    """
    Evaluates answerability for DOCUMENT_SUMMARY requests.
    Validates document availability, processing status, and page presence rather than
    relying on keyword coverage against top-k chunks.
    """
    if not doc_exists or not target_doc_id:
        msg = f"Target document '{target_filename or 'specified'}' not found in knowledge base."
        return AnswerabilityResult(
            status="not_answerable",
            answerable=False,
            confidence=0.0,
            supportingChunkIds=[],
            missingInformation=[msg],
            conflictingChunkIds=[],
            reason=msg
        )
    if processing_status != "completed" or page_count == 0:
        msg = f"Document '{target_filename or target_doc_id}' has not completed processing or contains 0 pages."
        return AnswerabilityResult(
            status="not_answerable",
            answerable=False,
            confidence=0.0,
            supportingChunkIds=[],
            missingInformation=[msg],
            conflictingChunkIds=[],
            reason=msg
        )
    return AnswerabilityResult(
        status="fully_answerable",
        answerable=True,
        confidence=0.98,
        supportingChunkIds=[f"{target_doc_id}#full-doc"],
        missingInformation=[],
        conflictingChunkIds=[],
        reason=f"Complete document '{target_filename or target_doc_id}' ({page_count} pages) is indexed and verified for full-document summarization."
    )
