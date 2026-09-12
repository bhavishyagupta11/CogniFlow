"""
Document Text Extraction and Chunking
Uses PyMuPDF (fitz) for fast PDF extraction and clean recursive character chunking.
"""

from typing import List, Dict, Any, Optional
import re
from pathlib import Path
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def extract_text_from_pdf(pdf_path: str | Path) -> List[Dict[str, Any]]:
    """
    Extracts text page-by-page from a PDF file.
    Normalizes whitespace and reconnects split list items.
    Returns a list of dicts: [{"pageNumber": 1, "text": "..."}]
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) is not installed.")
    
    pages = []
    doc = fitz.open(str(pdf_path))
    for i, page in enumerate(doc):
        text = page.get_text("text") or ""
        # Reconnect numbered lists like "1. \nTitle" -> "1. Title"
        text = re.sub(r"(\b\d{1,3}\.)\s*\n\s*", r"\1 ", text)
        # Reconnect bullet lists like "• \nItem" -> "• Item"
        text = re.sub(r"([•\-\*])\s*\n\s*", r"\1 ", text)
        # Clean extra horizontal whitespace
        cleaned = re.sub(r"[ \t]+", " ", text).strip()
        if cleaned:
            pages.append({
                "pageNumber": i + 1,
                "text": cleaned
            })
    doc.close()
    return pages


def is_heading(line: str) -> bool:
    """Detects whether a short line is likely a section heading."""
    line = line.strip()
    if not line or len(line) > 60:
        return False
    if re.match(r"^[A-Z][a-zA-Z0-9\s&/\-]{2,40}$", line):
        return True
    if line.endswith(":") and len(line) < 45:
        return True
    return False


def chunk_text(
    text: str,
    chunk_size: int = 700,
    chunk_overlap: int = 100,
    page_number: int = 1
) -> List[Dict[str, Any]]:
    """
    Splits text into chunks of roughly `chunk_size` characters with `chunk_overlap`.
    Preserves headings with their subsequent items and list boundaries.
    """
    if not text or not text.strip():
        return []

    # Normalize newlines
    normalized = re.sub(r"\r\n?", "\n", text).strip()
    
    # Split by double newlines or clear section boundaries
    raw_blocks = re.split(r"\n\s*\n", normalized)
    blocks = [b.strip() for b in raw_blocks if b.strip()]

    chunks = []
    current_chunk = ""
    current_section = "General"

    for block in blocks:
        # Check if block contains or begins with a section heading
        lines = block.split("\n")
        first_line = lines[0].strip()
        if is_heading(first_line):
            current_section = first_line

        # If adding this block exceeds chunk_size, push current and start new
        if len(current_chunk) + len(block) + 2 <= chunk_size:
            current_chunk = f"{current_chunk}\n\n{block}".strip() if current_chunk else block
        else:
            if current_chunk:
                chunks.append({
                    "text": current_chunk,
                    "pageNumber": page_number,
                    "section": current_section,
                    "character_count": len(current_chunk)
                })

            # If the block itself is huge, split by list items or sentences
            if len(block) > chunk_size:
                # Try splitting by list items first (e.g. "1. ", "2. ", "• ")
                list_items = re.split(r"(?=(?:^|\n)(?:\d{1,3}\.|[•\-\*])\s+)", block)
                sub_chunk = ""
                for item in list_items:
                    item = item.strip()
                    if not item:
                        continue
                    if len(sub_chunk) + len(item) + 2 <= chunk_size:
                        sub_chunk = f"{sub_chunk}\n{item}".strip() if sub_chunk else item
                    else:
                        if sub_chunk:
                            chunks.append({
                                "text": sub_chunk,
                                "pageNumber": page_number,
                                "section": current_section,
                                "character_count": len(sub_chunk)
                            })
                        sub_chunk = item
                if sub_chunk:
                    current_chunk = sub_chunk
                else:
                    current_chunk = ""
            else:
                current_chunk = block

    if current_chunk:
        chunks.append({
            "text": current_chunk,
            "pageNumber": page_number,
            "section": current_section,
            "character_count": len(current_chunk)
        })

    return [c for c in chunks if len(c["text"].strip()) >= 10]
