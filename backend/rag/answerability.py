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
    # Filter common stop words, determiners, prepositions, and conversational meta-terms
    stop_words = {
        "what", "when", "where", "which", "how", "why", "who", "does", "did", "do",
        "explain", "compare", "the", "and", "for", "with", "from", "into", "onto",
        "uploaded", "document", "documents", "file", "files", "pdf", "tell", "show",
        "please", "list", "about", "describe", "give", "definition", "define",
        "overview", "detail", "details", "their", "complete", "summary", "summay",
        "entire", "whole", "full", "this", "that", "these", "those", "there", "any",
        "some", "other", "another", "information", "info", "notes", "paper", "book",
        "text", "content", "read", "write", "provide", "data", "structures"
    }
    key_tokens = [t for t in q_tokens if t not in stop_words and len(t) >= 4]

    if not key_tokens:
        key_tokens = [t for t in q_tokens if len(t) >= 4]

    corpus_text = " ".join([s.get("chunkContent", s.get("content", "")) + " " + s.get("documentTitle", "") for s in sources]).lower()

    # 1. Conservative Contradiction Detection across chunks
    if len(sources) >= 2 and key_tokens:
        for i in range(len(sources)):
            for j in range(i + 1, len(sources)):
                c1_text = sources[i].get("chunkContent", sources[i].get("content", "")).lower()
                c2_text = sources[j].get("chunkContent", sources[j].get("content", "")).lower()

                doc1_id = sources[i].get("documentId") or sources[i].get("document_id") or "doc1"
                doc2_id = sources[j].get("documentId") or sources[j].get("document_id") or "doc2"
                doc1_title = sources[i].get("documentTitle") or sources[i].get("filename") or "Document 1"
                doc2_title = sources[j].get("documentTitle") or sources[j].get("filename") or "Document 2"

                for pos_pattern, neg_pattern in OPPOSING_PAIRS:
                    m_pos_1 = re.search(pos_pattern, c1_text)
                    m_neg_2 = re.search(neg_pattern, c2_text)
                    m_pos_2 = re.search(pos_pattern, c2_text)
                    m_neg_1 = re.search(neg_pattern, c1_text)

                    match_pair = None
                    if m_pos_1 and m_neg_2:
                        match_pair = (m_pos_1.start(), m_neg_2.start(), c1_text, c2_text)
                    elif m_pos_2 and m_neg_1:
                        match_pair = (m_pos_2.start(), m_neg_1.start(), c2_text, c1_text)

                    if match_pair:
                        p_pos, p_neg, text_pos, text_neg = match_pair
                        # Verify that the opposing assertion shares a substantive topic within proximity (<80 chars)
                        shared_subjects = []
                        for t in key_tokens:
                            # Substantive subject must appear close to the assertion verbs in both chunks
                            pos_sub = t in text_pos[max(0, p_pos - 80) : min(len(text_pos), p_pos + 80)]
                            neg_sub = t in text_neg[max(0, p_neg - 80) : min(len(text_neg), p_neg + 80)]
                            if pos_sub and neg_sub:
                                shared_subjects.append(t)

                        if shared_subjects:
                            id_i = sources[i].get("chunkId", sources[i].get("id", f"chunk-{i}"))
                            id_j = sources[j].get("chunkId", sources[j].get("id", f"chunk-{j}"))

                            # Distinguish across sources vs. within same document
                            if doc1_id != doc2_id:
                                prefix = f"Conflicting evidence detected across sources ({doc1_title} vs {doc2_title})"
                            else:
                                prefix = f"Conflicting passages within {doc1_title}"

                            return AnswerabilityResult(
                                status="contradictory",
                                answerable=True,
                                confidence=0.85,
                                supportingChunkIds=[id_i, id_j],
                                missingInformation=[],
                                conflictingChunkIds=[id_i, id_j],
                                coveredConcepts=shared_subjects,
                                missingConcepts=[],
                                reason=f"{prefix}: Opposing assertions detected regarding '{shared_subjects[0]}' between retrieved passages."
                            )

    # 2. Multi-Concept Coverage & Requirement Gating
    from backend.rag.concept_coverage import analyze_concept_coverage
    concept_res = analyze_concept_coverage(question, sources)

    # Gather supporting chunks that actually support covered concepts
    supporting_ids = []
    for concept in concept_res.covered_concepts:
        supporting_ids.extend(concept_res.concept_support.get(concept, []))
    supporting_ids = list(dict.fromkeys(supporting_ids))
    if not supporting_ids and concept_res.status != "not_answerable":
        supporting_ids = [s.get("chunkId", s.get("id", "")) for s in sources]

    if concept_res.status == "fully_answerable":
        return AnswerabilityResult(
            status="fully_answerable",
            answerable=True,
            confidence=round(0.85 + (concept_res.coverage_ratio * 0.14), 2),
            supportingChunkIds=supporting_ids,
            missingInformation=[],
            conflictingChunkIds=[],
            coveredConcepts=concept_res.covered_concepts,
            missingConcepts=[],
            reason=concept_res.reason
        )

    if concept_res.status == "partially_answerable":
        return AnswerabilityResult(
            status="partially_answerable",
            answerable=True,
            confidence=round(0.50 + (concept_res.coverage_ratio * 0.30), 2),
            supportingChunkIds=supporting_ids,
            missingInformation=concept_res.missing_concepts,
            conflictingChunkIds=[],
            coveredConcepts=concept_res.covered_concepts,
            missingConcepts=concept_res.missing_concepts,
            reason=concept_res.reason
        )

    return AnswerabilityResult(
        status="not_answerable",
        answerable=False,
        confidence=0.20,
        supportingChunkIds=[],
        missingInformation=concept_res.missing_concepts or ["Requested concepts are absent from the indexed literature."],
        conflictingChunkIds=[],
        coveredConcepts=[],
        missingConcepts=concept_res.missing_concepts or key_tokens[:3],
        reason=concept_res.reason or "Requested concepts are absent from the indexed literature."
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
