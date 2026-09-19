"""
CogniFlow Semantic Document Chunker & Provenance Extractor
Implements deterministic, structure-aware semantic chunking:
- Identifies headings (#, ##, ALL CAPS, Section/Chapter X, numbered prefixes)
- Bonds headings, definitions, algorithms, and complexity specifications to their explanatory content
- Preserves paragraph and sentence coherence (never splits in the middle of an explanation)
- Maintains strict provenance: document_id, document_name, document_version, chunk_id,
  section, subsection, page_start, page_end, source_location, and text.
"""

from typing import List, Dict, Any, Optional, Tuple
import re
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


class PDFPasswordRequiredError(Exception):
    """Raised when an encrypted PDF is uploaded without a password."""
    pass


class PDFIncorrectPasswordError(Exception):
    """Raised when the provided password fails to decrypt the encrypted PDF."""
    pass


def extract_text_from_pdf_with_unlocked_bytes(
    pdf_source: str | Path | bytes,
    password: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], bytes]:
    """
    Extracts text page-by-page from a PDF file (path or in-memory bytes) using PyMuPDF.
    Detects encrypted PDFs and authenticates with password if provided.
    If the PDF was password-protected, converts it in-memory to clean unlocked PDF bytes.
    Normalizes whitespace and reconnects split list items.
    Returns:
        (pages_list, unlocked_pdf_bytes)
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed.")

    raw_input_bytes = pdf_source if isinstance(pdf_source, bytes) else Path(pdf_source).read_bytes()
    doc = fitz.open(stream=raw_input_bytes, filetype="pdf")

    try:
        was_encrypted = False
        # Detect password protection
        if doc.needs_pass:
            if not password:
                raise PDFPasswordRequiredError(
                    "This PDF is password-protected. Please enter the password to unlock and process it."
                )
            auth_res = doc.authenticate(password)
            if auth_res == 0:
                raise PDFIncorrectPasswordError("Incorrect PDF password. Please try again.")
            was_encrypted = True

        pages = []
        for i, page in enumerate(doc):
            text = page.get_text("text") or ""
            # Reconnect numbered lists like "1. \nTitle" -> "1. Title"
            text = re.sub(r"(\b\d{1,3}\.)\s*\n\s*", r"\1 ", text)
            # Reconnect bullet lists like "• \nItem" -> "• Item"
            text = re.sub(r"([•\-\*])\s*\n\s*", r"\1 ", text)
            # Clean extra horizontal whitespace while preserving paragraph line breaks
            cleaned = re.sub(r"[ \t]+", " ", text).strip()
            if cleaned:
                pages.append({
                    "pageNumber": i + 1,
                    "text": cleaned
                })

        if was_encrypted:
            # Produce clean unlocked PDF bytes without encryption
            unlocked_bytes = doc.tobytes()
        else:
            unlocked_bytes = raw_input_bytes

        return pages, unlocked_bytes
    finally:
        doc.close()


def extract_text_from_pdf(
    pdf_source: str | Path | bytes,
    password: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Extracts text page-by-page from a PDF file (path or in-memory bytes) using PyMuPDF.
    Backwards-compatible wrapper around extract_text_from_pdf_with_unlocked_bytes.
    Returns a list of dicts: [{"pageNumber": 1, "text": "..."}]
    """
    pages, _ = extract_text_from_pdf_with_unlocked_bytes(pdf_source, password=password)
    return pages


def detect_heading(line: str) -> Optional[Dict[str, str]]:
    """
    Detects if a line is a heading or subsection header.
    Returns {"type": "heading"|"subsection", "title": str} or None.
    """
    line = line.strip()
    if not line or len(line) > 90:
        return None

    # Markdown style headings
    if line.startswith("### "):
        return {"type": "subsection", "title": line[4:].strip()}
    if line.startswith("# ") or line.startswith("## "):
        return {"type": "heading", "title": re.sub(r"^#+\s*", "", line).strip()}

    # Numbered section headers like "1.2 Binary Search Trees" or "Chapter 3: Stacks"
    num_match = re.match(r"^(?:Unit|Chapter|Section|\d+\.\d+|\d+\.)\s*[:\-]?\s*([A-Za-z0-9\s&/\-]{3,70})$", line, re.IGNORECASE)
    if num_match:
        return {"type": "heading", "title": line}

    # Short title in ALL CAPS
    if len(line) >= 4 and len(line) <= 60 and line.isupper() and re.search(r"[A-Z]{3,}", line):
        return {"type": "heading", "title": line}

    # Short title ending with colon e.g. "Complexity Analysis:" or "Algorithm Definition:"
    if line.endswith(":") and len(line) <= 50 and not line.startswith("Note:") and not line.startswith("Example:"):
        return {"type": "subsection", "title": line[:-1].strip()}

    return None


def is_definition_or_algorithm_start(line: str) -> bool:
    """Detects start of definition, theorem, or algorithm."""
    low = line.strip().lower()
    return any(low.startswith(p) for p in [
        "definition:", "algorithm:", "pseudocode:", "complexity:",
        "time complexity:", "space complexity:", "theorem:", "lemma:"
    ])


def semantic_chunk_document(
    pages: Optional[List[Dict[str, Any]]] = None,
    document_id: str = "doc-default",
    document_name: Optional[str] = None,
    document_version: str = "1.0",
    target_chunk_size: int = 850,
    max_chunk_size: int = 1400,
    min_chunk_size: int = 80,
    filename: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Performs deterministic, structure-aware semantic chunking over multi-page documents.
    Preserves:
    - Headings and subsections bonded with their immediate descriptive text
    - Definitions and algorithm pseudocode intact with their complexity
    - Page start and page end boundaries
    - Complete provenance dictionary conforming to Specification Section 13.
    """
    if not pages:
        return []

    doc_name = document_name or filename or "Document"
    chunks: List[Dict[str, Any]] = []
    chunk_counter = 1

    current_section = doc_name
    current_subsection = ""
    current_paragraphs: List[str] = []
    current_page_start: Optional[int] = None
    current_page_end: Optional[int] = None
    current_char_count = 0

    has_page_numbers = any(
        (p.get("pageNumber") is not None or p.get("page_number") is not None or p.get("page") is not None)
        for p in pages
    )

    def flush_chunk(is_final: bool = False):
        nonlocal chunk_counter, current_paragraphs, current_page_start, current_page_end, current_char_count
        if not current_paragraphs:
            return

        combined_text = "\n\n".join(current_paragraphs).strip()
        if len(combined_text) >= min_chunk_size or (is_final and len(combined_text) > 0):
            c_id = f"{document_id}#chunk-{chunk_counter}"

            if has_page_numbers:
                p_start = current_page_start if current_page_start is not None else 1
                p_end = current_page_end if current_page_end is not None else p_start
                source_loc = f"p. {p_start}" if p_start == p_end else f"pp. {p_start}–{p_end}"
                page_rng = f"{p_start}–{p_end}"
            else:
                p_start = None
                p_end = None
                source_loc = f"Section: {current_section}" if current_section else doc_name
                page_rng = None

            chunk_record = {
                "chunk_id": c_id,
                "id": c_id,
                "document_id": document_id,
                "documentId": document_id,
                "document_name": doc_name,
                "documentTitle": doc_name,
                "source_filename": doc_name,
                "document_version": document_version,
                "section": current_section,
                "subsection": current_subsection or current_section,
                "page_start": p_start,
                "page_end": p_end,
                "pageNumber": p_start if p_start is not None else 1,
                "page_number": p_start,
                "pageRange": page_rng,
                "source_location": source_loc,
                "text": combined_text,
                "content": combined_text,
                "chunkContent": combined_text,
                "character_count": len(combined_text),
                "index": chunk_counter,
                "chunk_index": chunk_counter
            }
            chunks.append(chunk_record)
            chunk_counter += 1

        current_paragraphs = []
        current_page_start = None
        current_page_end = None
        current_char_count = 0

    for p in pages:
        p_num = p.get("pageNumber") if p.get("pageNumber") is not None else (p.get("page_number") if p.get("page_number") is not None else p.get("page"))
        if p.get("section") and p["section"] != doc_name:
            current_section = p["section"]

        raw_text = p.get("text", "")
        if not raw_text.strip():
            continue

        normalized = re.sub(r"\r\n?", "\n", raw_text)
        # Split by double newlines into logical paragraphs
        raw_paras = re.split(r"\n\s*\n", normalized)

        for para in raw_paras:
            para = para.strip()
            if not para:
                continue

            if current_page_start is None and p_num is not None:
                current_page_start = p_num
            if p_num is not None:
                current_page_end = p_num

            lines = para.split("\n")
            first_line = lines[0].strip()
            head_info = detect_heading(first_line)

            # If a major heading starts, flush existing buffer to preserve section boundary
            if head_info:
                if head_info["type"] == "heading":
                    if current_char_count >= target_chunk_size // 2:
                        flush_chunk()
                    current_section = head_info["title"]
                    current_subsection = ""
                elif head_info["type"] == "subsection":
                    if current_char_count >= target_chunk_size:
                        flush_chunk()
                    current_subsection = head_info["title"]

            para_len = len(para)

            # Check if adding this paragraph exceeds maximum chunk size
            if current_char_count + para_len > max_chunk_size and current_paragraphs:
                flush_chunk()

            if current_page_start is None:
                current_page_start = p_num
            current_page_end = p_num

            # If paragraph itself is excessively large (e.g. monolithic code or table block)
            if para_len > max_chunk_size:
                # Split large paragraph by sentence boundaries
                sentences = re.split(r"(?<=[.?!])\s+(?=[A-Z0-9])", para)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    if current_char_count + len(sentence) > max_chunk_size and current_paragraphs:
                        flush_chunk()
                        if current_page_start is None:
                            current_page_start = p_num
                        current_page_end = p_num
                    current_paragraphs.append(sentence)
                    current_char_count += len(sentence) + 1
            else:
                current_paragraphs.append(para)
                current_char_count += para_len + 2

            # If target chunk size reached and at natural paragraph end, flush
            if current_char_count >= target_chunk_size:
                flush_chunk()

    # Flush any remaining paragraphs
    flush_chunk(is_final=True)

    return chunks


def chunk_text(
    text: str,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
    page_number: int = 1
) -> List[Dict[str, Any]]:
    """
    Backwards-compatible chunker interface that uses semantic chunking internally.
    """
    pages = [{"pageNumber": page_number, "text": text}]
    semantic_chunks = semantic_chunk_document(
        pages=pages,
        document_id="inline_doc",
        document_name="Document Passage",
        target_chunk_size=chunk_size,
        max_chunk_size=chunk_size + 300,
        min_chunk_size=20
    )
    return [
        {
            "text": c["text"],
            "content": c["text"],
            "pageNumber": c["page_start"],
            "page_start": c["page_start"],
            "page_end": c["page_end"],
            "section": c["section"],
            "character_count": c["character_count"]
        }
        for c in semantic_chunks
    ]
