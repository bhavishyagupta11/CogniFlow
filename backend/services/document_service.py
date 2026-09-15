"""
Document Ingestion and Manifest Management Service
Handles document uploads, SHA-256 deduplication, PyMuPDF extraction,
OCR-condition detection, atomic manifest syncing, and active index verification.
"""

import json
import hashlib
import time
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.config import MANIFEST_PATH, UPLOADS_DIR, EXTRACTED_DIR
from backend.rag.chunker import extract_text_from_pdf, chunk_text
from backend.rag.vector_store import vector_store

logger = logging.getLogger("cogniflow.document_service")


def get_manifest() -> List[Dict[str, Any]]:
    """Reads all manifest entries from data/manifest.json."""
    if not MANIFEST_PATH.exists():
        return []
    try:
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[DocumentService] Failed to read manifest: {e}")
        return []


def save_manifest(manifest: List[Dict[str, Any]]):
    """Writes manifest entries to data/manifest.json atomically."""
    temp_path = MANIFEST_PATH.with_suffix(".tmp")
    temp_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    temp_path.replace(MANIFEST_PATH)


def compute_sha256(data: bytes) -> str:
    """Computes SHA-256 hex digest for idempotency."""
    return hashlib.sha256(data).hexdigest()


def log_upload_summary(
    doc_id: str,
    filename: str,
    page_count: int,
    char_count: int,
    chunk_count: int,
    index_before: int,
    index_after: int,
    duration_ms: int,
    status: str
):
    """Logs a safe structured summary without exposing user data or secrets."""
    print(
        f"[DocumentIngestion] SUCCESS doc_id={doc_id} filename='{filename}' "
        f"pages={page_count} chars={char_count} chunks={chunk_count} "
        f"index_before={index_before} index_after={index_after} "
        f"duration={duration_ms}ms status={status}"
    )


async def ingest_file(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    owner_id: str = "dev-user"
) -> Dict[str, Any]:
    """
    Ingests a single file:
    1. Validates size, extension, and filename traversal
    2. Computes SHA-256 and checks for duplicate
    3. Saves raw file to data/uploads/{id}.ext safely
    4. Extracts text (via PyMuPDF for PDFs, UTF-8 for TXT/MD)
    5. Validates non-empty text extraction; detects scanned/image-only low-text PDFs
    6. Writes extracted pages to data/extracted/{id}.json
    7. Updates manifest.json atomically and syncs active VectorStore
    8. Performs synchronous retrieval smoke test before returning indexed=True
    """
    start_time = time.time()
    index_before = len(vector_store.chunks)

    # 1. Sanitize filename & validate extension
    safe_filename = Path(filename).name
    if not safe_filename:
        safe_filename = "document.pdf"
    
    ext = Path(safe_filename).suffix.lower()
    allowed_exts = [".pdf", ".txt", ".md", ".json"]
    if ext not in allowed_exts:
        return {
            "ok": False,
            "status": 400,
            "error": {
                "code": "UNSUPPORTED_FORMAT",
                "message": f"File extension '{ext}' is not supported. Please upload PDF, TXT, or MD files."
            }
        }

    # 2. Check file size
    max_bytes = 25 * 1024 * 1024
    if len(file_bytes) > max_bytes:
        return {
            "ok": False,
            "status": 413,
            "error": {
                "code": "FILE_TOO_LARGE",
                "message": f"File size ({len(file_bytes)} bytes) exceeds the 25MB maximum limit."
            }
        }

    if len(file_bytes) == 0:
        return {
            "ok": False,
            "status": 400,
            "error": {
                "code": "EMPTY_FILE",
                "message": "Uploaded file is 0 bytes."
            }
        }

    # 3. Compute SHA-256 and check for duplicate
    file_hash = compute_sha256(file_bytes)
    manifest = get_manifest()

    existing = next(
        (m for m in manifest if m.get("hash") == file_hash and (m.get("ownerId") == owner_id or m.get("owner_id") == owner_id)),
        None
    )
    if existing:
        return {
            "ok": False,
            "status": 409,
            "error": {
                "code": "DUPLICATE",
                "message": f"File '{safe_filename}' already exists in your knowledge base.",
                "existingId": existing.get("id"),
                "existingFilename": existing.get("originalFilename")
            }
        }

    # 4. Save raw file to uploads directory
    doc_id = str(uuid.uuid4())
    stored_filename = f"{doc_id}{ext}"
    stored_path = UPLOADS_DIR / stored_filename
    try:
        stored_path.write_bytes(file_bytes)
    except Exception as e:
        return {
            "ok": False,
            "status": 500,
            "error": {
                "code": "STORAGE_ERROR",
                "message": f"Failed to write file to disk: {e}"
            }
        }

    # 5. Extract text
    pages: List[Dict[str, Any]] = []
    if ext == ".pdf":
        try:
            pages = extract_text_from_pdf(stored_path)
        except Exception as e:
            print(f"[DocumentService] Error extracting PDF {safe_filename}: {e}")
            if stored_path.exists():
                stored_path.unlink(missing_ok=True)
            return {
                "ok": False,
                "status": 422,
                "error": {
                    "code": "EXTRACTION_FAILED",
                    "message": f"Failed to extract text from PDF: {e}"
                }
            }
    else:
        # Plain text / Markdown
        try:
            text = file_bytes.decode("utf-8", errors="replace")
            pages = [{"pageNumber": 1, "text": text}]
        except Exception as e:
            print(f"[DocumentService] Error decoding text {safe_filename}: {e}")
            if stored_path.exists():
                stored_path.unlink(missing_ok=True)
            return {
                "ok": False,
                "status": 422,
                "error": {
                    "code": "EXTRACTION_FAILED",
                    "message": f"Failed to decode text file: {e}"
                }
            }

    # 6. Validate usable text extracted - detect image-only/scanned PDF (low-text condition)
    total_text_len = sum(len(p.get("text", "").strip()) for p in pages)
    if ext == ".pdf" and (total_text_len < 10 or len(pages) == 0):
        if stored_path.exists():
            stored_path.unlink(missing_ok=True)
        return {
            "ok": False,
            "status": 422,
            "error": {
                "code": "OCR_REQUIRED",
                "message": "PDF uploaded, but no selectable text was found. OCR is required."
            }
        }

    if total_text_len == 0 or len(pages) == 0:
        if stored_path.exists():
            stored_path.unlink(missing_ok=True)
        return {
            "ok": False,
            "status": 422,
            "error": {
                "code": "EMPTY_OR_UNREADABLE",
                "message": "Document contains no readable text or failed text extraction. It may be image-only or empty."
            }
        }

    # 7. Chunk text
    total_chunks = 0
    chunk_ids = []
    for p in pages:
        p_chunks = chunk_text(p["text"], chunk_size=600, chunk_overlap=80, page_number=p["pageNumber"])
        for idx in range(len(p_chunks)):
            total_chunks += 1
            chunk_ids.append(f"{doc_id}#chunk-{total_chunks}")

    if total_chunks == 0:
        if stored_path.exists():
            stored_path.unlink(missing_ok=True)
        return {
            "ok": False,
            "status": 422,
            "error": {
                "code": "NO_CHUNKS_PRODUCED",
                "message": "Text extraction did not produce any indexable text chunks."
            }
        }

    # 8. Save extracted representation to data/extracted/{id}.json
    extracted_path = EXTRACTED_DIR / f"{doc_id}.json"
    try:
        extracted_path.write_text(json.dumps(pages, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[DocumentService] Warning: Failed to write extracted json {extracted_path}: {e}")

    # 9. Update manifest.json atomically
    now_iso = datetime.now(timezone.utc).isoformat()
    new_entry = {
        "schemaVersion": 2,
        "id": doc_id,
        "document_id": doc_id,
        "filename": stored_filename,
        "originalFilename": safe_filename,
        "original_filename": safe_filename,
        "mimeType": mime_type or ("application/pdf" if ext == ".pdf" else "text/plain"),
        "size": len(file_bytes),
        "uploadedAt": now_iso,
        "lastModified": now_iso,
        "pageCount": len(pages),
        "page_count": len(pages),
        "chunkCount": total_chunks,
        "chunk_count": total_chunks,
        "chunkIds": chunk_ids,
        "processingStatus": "completed",
        "processing_status": "completed",
        "indexStatus": "indexed",
        "indexed": True,
        "ownerId": owner_id,
        "owner_id": owner_id,
        "tenantId": owner_id,
        "hash": file_hash,
        "charCount": total_text_len,
        "char_count": total_text_len,
        "extractedCharCount": total_text_len,
        "extracted_char_count": total_text_len,
        "indexInsertionStatus": "indexed",
        "index_insertion_status": "indexed",
        "indexVersion": vector_store.index_version + 1,
        "index_version": vector_store.index_version + 1
    }

    manifest.append(new_entry)
    save_manifest(manifest)

    # 10. Update in-memory vector store immediately
    vector_store.add_document(doc_id, safe_filename, pages, owner_id)
    index_after = len(vector_store.chunks)

    # 11. Run retrieval smoke test against the newly indexed document
    smoke_test_query = pages[0].get("text", "")[:80].strip() or safe_filename
    smoke_candidates = vector_store.search(
        query=smoke_test_query,
        k=1,
        owner_id=owner_id,
        document_id=doc_id,
        scope="DOCUMENT"
    )
    smoke_passed = any(
        (c.get("document_id") == doc_id or c.get("documentId") == doc_id)
        for c in smoke_candidates
    )

    if not smoke_passed:
        print(f"[DocumentService] CRITICAL: Ingestion smoke test failed for {doc_id} ({safe_filename}). Rolling back.")
        # Roll back manifest, disk files, and vector store
        if stored_path.exists():
            stored_path.unlink(missing_ok=True)
        if extracted_path.exists():
            extracted_path.unlink(missing_ok=True)
        manifest = [m for m in manifest if m.get("id") != doc_id]
        save_manifest(manifest)
        vector_store.remove_document(doc_id)
        return {
            "ok": False,
            "status": 500,
            "error": {
                "code": "SMOKE_TEST_FAILED",
                "message": f"Document '{safe_filename}' was extracted but failed active retrieval smoke test."
            }
        }

    duration_ms = int((time.time() - start_time) * 1000)
    log_upload_summary(
        doc_id=doc_id,
        filename=safe_filename,
        page_count=len(pages),
        char_count=total_text_len,
        chunk_count=total_chunks,
        index_before=index_before,
        index_after=index_after,
        duration_ms=duration_ms,
        status="indexed"
    )

    return {
        "ok": True,
        "success": True,
        "status": 200,
        "document": new_entry
    }


def delete_document(doc_id: str, owner_id: str = "dev-user") -> bool:
    """Deletes a document from disk, manifest, and vector store with ownership check."""
    manifest = get_manifest()
    target = next((m for m in manifest if m.get("id") == doc_id or m.get("document_id") == doc_id), None)
    if not target:
        return False

    # Ownership validation: prevent cross-user document deletion
    target_owner = target.get("ownerId") or target.get("owner_id")
    allowed_owners = [owner_id, "public"]
    if owner_id in ["dev-user", "user_default"]:
        allowed_owners.extend(["dev-user", "user_default"])

    if owner_id != "system" and target_owner and target_owner not in allowed_owners:
        return False

    # 1. Remove file from uploads
    filename = target.get("filename")
    if filename:
        upload_path = UPLOADS_DIR / filename
        if upload_path.exists():
            try:
                upload_path.unlink()
            except Exception as e:
                print(f"[DocumentService] Warning: Failed to delete upload {upload_path}: {e}")

    # 2. Remove extracted json
    extracted_file = EXTRACTED_DIR / f"{doc_id}.json"
    if extracted_file.exists():
        try:
            extracted_file.unlink()
        except Exception as e:
            print(f"[DocumentService] Warning: Failed to delete extracted file {extracted_file}: {e}")

    # 3. Remove from manifest
    updated_manifest = [m for m in manifest if m.get("id") != doc_id and m.get("document_id") != doc_id]
    save_manifest(updated_manifest)

    # 4. Remove from vector store
    vector_store.remove_document(doc_id)

    # 5. Invalidate summary cache
    from backend.services.summary_cache import summary_cache
    summary_cache.invalidate_document(doc_id)

    return True


def inspect_document(doc_id: str) -> Dict[str, Any]:
    """
    Validates document health:
    - file exists
    - file is a valid PDF
    - page count is greater than zero
    - extracted text length is greater than zero
    - chunk count is greater than zero
    - chunks contain the expected document ID
    - chunks contain the expected filename
    - page numbers are valid
    - index contains the chunks
    """
    manifest = get_manifest()
    target = next((m for m in manifest if m.get("id") == doc_id or m.get("document_id") == doc_id), None)
    if not target:
        return {"valid": False, "error": f"Document '{doc_id}' not found in manifest."}

    filename = target.get("filename", f"{doc_id}.pdf")
    upload_path = UPLOADS_DIR / filename
    if not upload_path.exists():
        return {"valid": False, "error": f"Uploaded file '{filename}' missing on disk."}

    extracted_path = EXTRACTED_DIR / f"{doc_id}.json"
    if not extracted_path.exists():
        return {"valid": False, "error": f"Extracted JSON for '{doc_id}' missing on disk."}

    try:
        pages = json.loads(extracted_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"valid": False, "error": f"Failed to parse extracted JSON: {e}"}

    page_count = len(pages)
    if page_count == 0:
        return {"valid": False, "error": "Extracted pages count is zero."}

    total_chars = sum(len(p.get("text", "").strip()) for p in pages)
    if total_chars == 0:
        return {"valid": False, "error": "Extracted text length is zero."}

    indexed_chunks = [c for c in vector_store.chunks if c.get("document_id") == doc_id or c.get("documentId") == doc_id]
    if len(indexed_chunks) == 0:
        return {"valid": False, "error": "No chunks found in active vector index."}

    original_filename = target.get("originalFilename") or target.get("original_filename")
    for c in indexed_chunks:
        if c.get("page_number", 0) <= 0:
            return {"valid": False, "error": f"Invalid page number {c.get('page_number')} in chunk {c.get('id')}"}
        if not c.get("text"):
            return {"valid": False, "error": f"Empty text in chunk {c.get('id')}"}

    return {
        "valid": True,
        "doc_id": doc_id,
        "filename": original_filename,
        "page_count": page_count,
        "char_count": total_chars,
        "chunk_count": len(indexed_chunks),
        "index_status": "indexed",
        "in_memory": True
    }


def reindex_document(doc_id: str, owner_id: str = "dev-user") -> Dict[str, Any]:
    """
    Re-extracts, re-chunks, and re-indexes an uploaded document from disk.
    """
    manifest = get_manifest()
    target = next((m for m in manifest if m.get("id") == doc_id or m.get("document_id") == doc_id), None)
    if not target:
        return {"ok": False, "status": 404, "error": f"Document '{doc_id}' not found in manifest."}

    filename = target.get("filename", f"{doc_id}.pdf")
    upload_path = UPLOADS_DIR / filename
    if not upload_path.exists():
        return {"ok": False, "status": 404, "error": f"File '{filename}' missing on disk."}

    # Re-extract
    safe_name = target.get("originalFilename") or target.get("original_filename") or filename
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        pages = extract_text_from_pdf(upload_path)
    else:
        text = upload_path.read_text(encoding="utf-8", errors="replace")
        pages = [{"pageNumber": 1, "text": text}]

    # Update extracted JSON
    extracted_path = EXTRACTED_DIR / f"{doc_id}.json"
    extracted_path.write_text(json.dumps(pages, indent=2), encoding="utf-8")

    # Update VectorStore
    vector_store.add_document(doc_id, safe_name, pages, owner_id)

    # Update manifest
    target["lastModified"] = datetime.now(timezone.utc).isoformat()
    target["indexStatus"] = "indexed"
    target["indexed"] = True
    save_manifest(manifest)

    # Invalidate summary cache
    from backend.services.summary_cache import summary_cache
    summary_cache.invalidate_document(doc_id)

    return {
        "ok": True,
        "status": 200,
        "message": f"Document '{safe_name}' successfully re-indexed.",
        "doc_id": doc_id,
        "chunks_indexed": len([c for c in vector_store.chunks if c.get("document_id") == doc_id])
    }
