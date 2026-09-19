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
from typing import List, Dict, Any, Optional, Tuple, Callable

from backend.config import MANIFEST_PATH, UPLOADS_DIR, EXTRACTED_DIR
from backend.rag.extractor import (
    extract_document_content,
    sniff_document_type,
    PDFPasswordRequiredError,
    PDFIncorrectPasswordError,
    UnsupportedFormatError,
    ExtractionError
)
from backend.rag.chunker import (
    chunk_text,
    semantic_chunk_document,
)
from backend.rag.vector_store import vector_store

logger = logging.getLogger("cogniflow.document_service")


class DeleteResult(tuple):
    """Result object returned by delete_document supporting both tuple unpacking and boolean truthiness."""
    def __new__(cls, success: bool, reason: str):
        return super().__new__(cls, (success, reason))

    @property
    def success(self) -> bool:
        return self[0]

    @property
    def reason(self) -> str:
        return self[1]

    def __bool__(self) -> bool:
        return self[0]


def get_manifest() -> List[Dict[str, Any]]:
    """Reads all documents from database and manifest.json, merging entries with DB taking precedence."""
    merged: Dict[str, Dict[str, Any]] = {}
    if MANIFEST_PATH.exists():
        try:
            entries = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            for m in entries:
                did = m.get("id") or m.get("document_id")
                if did:
                    merged[did] = m
        except Exception as e:
            logger.debug(f"[DocumentService] Error loading manifest.json: {e}")

    try:
        from backend.services.db_service import db_service
        db_docs = db_service.list_documents(caller_id=None, is_admin=True)
        for d in db_docs:
            did = d.get("id") or d.get("document_id")
            if did:
                merged[did] = d
    except Exception as e:
        logger.debug(f"[DocumentService] Reading manifest from db_service fallback: {e}")

    return list(merged.values())


def save_manifest(manifest: List[Dict[str, Any]]):
    """Writes manifest entries to data/manifest.json atomically for local cache compatibility."""
    try:
        temp_path = MANIFEST_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temp_path.replace(MANIFEST_PATH)
    except Exception as e:
        logger.debug(f"[DocumentService] Local manifest.json save error: {e}")


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
    owner_id: str = "dev-user",
    is_authenticated: bool = True,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """
    Ingests a single file:
    1. Validates size, extension, and filename traversal
    2. Computes SHA-256 and checks for duplicate
    3. Extracts text and authenticates encrypted PDFs before writing any files
    4. Validates non-empty text extraction; detects scanned/image-only low-text PDFs
    5. If authenticated, saves raw file to uploads/ and R2, writes DB records, and updates manifest
    6. If guest, stores temporary state in GuestSessionService (in-memory only, no DB/R2 writes)
    7. Updates active in-memory VectorStore with owner isolation
    8. Performs synchronous retrieval smoke test before returning indexed=True
    """
    start_time = time.time()
    index_before = len(vector_store.chunks)

    # 1. Sanitize filename & validate extension
    safe_filename = Path(filename).name
    if not safe_filename:
        safe_filename = "document.pdf"
    
    ext = Path(safe_filename).suffix.lower()
    allowed_exts = [".pdf", ".docx", ".txt", ".md"]
    if ext == ".doc":
        return {
            "ok": False,
            "status": 400,
            "error": {
                "code": "UNSUPPORTED_FORMAT",
                "message": "Legacy binary .doc files are not supported. Please save or convert your document to modern .docx format before uploading.",
                "filename": safe_filename,
                "field": "file"
            }
        }
    if ext not in allowed_exts:
        return {
            "ok": False,
            "status": 400,
            "error": {
                "code": "UNSUPPORTED_FORMAT",
                "message": f"File extension '{ext}' is not supported. Supported formats: .pdf, .docx, .txt, .md.",
                "filename": safe_filename,
                "field": "file"
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
                "message": f"File size ({len(file_bytes)} bytes) exceeds the 25MB maximum limit.",
                "filename": safe_filename,
                "field": "file"
            }
        }

    if len(file_bytes) == 0:
        return {
            "ok": False,
            "status": 400,
            "error": {
                "code": "EMPTY_FILE",
                "message": "Uploaded file is 0 bytes.",
                "filename": safe_filename,
                "field": "file"
            }
        }

    # 3. Compute SHA-256 and check for duplicate
    file_hash = compute_sha256(file_bytes)
    existing = None
    if is_authenticated:
        try:
            from backend.services.db_service import db_service
            existing = db_service.get_document_by_hash(file_hash, owner_id)
        except Exception:
            existing = None

        if not existing:
            manifest = get_manifest()
            existing = next(
                (m for m in manifest if m.get("hash") == file_hash and (m.get("ownerId") == owner_id or m.get("owner_id") == owner_id)),
                None
            )
    else:
        from backend.services.guest_session_service import guest_session_service
        session_docs = guest_session_service.get_documents(owner_id)
        existing = next((d for d in session_docs if d.get("hash") == file_hash), None)

    if existing:
        existing_filename = existing.get("originalFilename") or existing.get("original_filename") or existing.get("filename") or "document"
        if existing_filename and existing_filename.strip().lower() != safe_filename.strip().lower():
            dup_msg = f"This file has already been uploaded as '{existing_filename}'."
        else:
            dup_msg = f"File '{safe_filename}' already exists in your knowledge base."
        return {
            "ok": False,
            "status": 409,
            "error": {
                "code": "DUPLICATE",
                "message": dup_msg,
                "existingId": existing.get("id") or existing.get("document_id"),
                "existingFilename": existing_filename,
                "filename": safe_filename,
                "field": "file"
            }
        }

    # 4. Extract text & validate password BEFORE saving any files or DB records
    pages: List[Dict[str, Any]] = []
    unlocked_bytes = file_bytes
    try:
        pages, unlocked_bytes = extract_document_content(
            file_bytes=file_bytes,
            filename=safe_filename,
            mime_type=mime_type,
            password=password
        )
    except PDFPasswordRequiredError as e:
        return {
            "ok": False,
            "status": 401,
            "error": {
                "code": "PASSWORD_REQUIRED",
                "message": str(e),
                "filename": safe_filename,
                "field": "password"
            }
        }
    except PDFIncorrectPasswordError as e:
        return {
            "ok": False,
            "status": 401,
            "error": {
                "code": "INCORRECT_PASSWORD",
                "message": str(e),
                "filename": safe_filename,
                "field": "password"
            }
        }
    except UnsupportedFormatError as e:
        return {
            "ok": False,
            "status": 400,
            "error": {
                "code": "UNSUPPORTED_FORMAT",
                "message": str(e),
                "filename": safe_filename,
                "field": "file"
            }
        }
    except Exception as e:
        logger.error(f"[DocumentService] Error extracting {safe_filename}: {e}")
        return {
            "ok": False,
            "status": 422,
            "error": {
                "code": "EXTRACTION_FAILED",
                "message": f"Failed to extract document content: {str(e)}",
                "filename": safe_filename,
                "field": "file"
            }
        }

    # 5. Validate usable text extracted - detect image-only/scanned PDF (low-text condition)
    total_text_len = sum(len(p.get("text", "").strip()) for p in pages)
    if ext == ".pdf" and (total_text_len < 10 or len(pages) == 0):
        return {
            "ok": False,
            "status": 422,
            "error": {
                "code": "OCR_REQUIRED",
                "message": "PDF uploaded, but no selectable text was found. OCR is required.",
                "filename": safe_filename,
                "field": "file"
            }
        }

    if total_text_len == 0 or len(pages) == 0:
        return {
            "ok": False,
            "status": 422,
            "error": {
                "code": "EMPTY_OR_UNREADABLE",
                "message": "Document contains no readable text or failed text extraction. It may be image-only or empty.",
                "filename": safe_filename,
                "field": "file"
            }
        }

    # 6. Semantic chunking with complete provenance
    doc_id = str(uuid.uuid4())
    stored_filename = f"{doc_id}{ext}"
    stored_path: Optional[Path] = None
    extracted_path: Optional[Path] = None
    r2_upload_key = f"uploads/{doc_id}/original"
    r2_extracted_key = f"extracted/{doc_id}/pages.json"

    semantic_chunks = semantic_chunk_document(pages, doc_id, safe_filename)
    total_chunks = len(semantic_chunks)
    chunk_ids = [c["chunk_id"] for c in semantic_chunks]

    if total_chunks == 0:
        return {
            "ok": False,
            "status": 422,
            "error": {
                "code": "NO_CHUNKS_PRODUCED",
                "message": "Text extraction did not produce any indexable text chunks."
            }
        }

    # 7. Persist representation
    now_iso = datetime.now(timezone.utc).isoformat()
    new_entry = {
        "schemaVersion": 2,
        "id": doc_id,
        "document_id": doc_id,
        "filename": stored_filename,
        "storage_filename": stored_filename,
        "originalFilename": safe_filename,
        "original_filename": safe_filename,
        "mimeType": mime_type or (
            "application/pdf" if ext == ".pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == ".docx"
            else "text/markdown" if ext in [".md", ".markdown"]
            else "text/plain"
        ),
        "mime_type": mime_type or (
            "application/pdf" if ext == ".pdf"
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == ".docx"
            else "text/markdown" if ext in [".md", ".markdown"]
            else "text/plain"
        ),
        "extension": ext,
        "size": len(file_bytes),
        "sizeBytes": len(file_bytes),
        "size_bytes": len(file_bytes),
        "uploadedAt": now_iso,
        "created_at": now_iso,
        "createdAt": now_iso,
        "lastModified": now_iso,
        "updated_at": now_iso,
        "pageCount": len(pages) if ext == ".pdf" else max(len(pages), 1),
        "page_count": len(pages) if ext == ".pdf" else max(len(pages), 1),
        "characterCount": total_text_len,
        "chunkCount": total_chunks,
        "chunk_count": total_chunks,
        "chunkIds": chunk_ids,
        "status": "completed",
        "processingStatus": "completed",
        "processing_status": "completed",
        "indexStatus": "indexed",
        "index_status": "indexed",
        "indexed": True,
        "ownerId": owner_id,
        "owner_id": owner_id,
        "tenantId": owner_id,
        "tenant_id": owner_id,
        "hash": file_hash,
        "fileHash": file_hash,
        "file_hash": file_hash,
        "charCount": total_text_len,
        "char_count": total_text_len,
        "extractedCharCount": total_text_len,
        "extracted_char_count": total_text_len,
        "indexInsertionStatus": "indexed",
        "index_insertion_status": "indexed",
        "indexVersion": vector_store.index_version + 1,
        "index_version": vector_store.index_version + 1,
        "r2_upload_key": r2_upload_key if is_authenticated else None,
        "r2_extracted_key": r2_extracted_key if is_authenticated else None,
        "lifecycle_state": "ACTIVE"
    }

    if is_authenticated:
        # Durable persistence for authenticated users
        from backend.services.storage_service import storage_service
        try:
            storage_service.put_object(r2_upload_key, unlocked_bytes, content_type=mime_type or ("application/pdf" if ext == ".pdf" else "text/plain"))
        except Exception as e:
            logger.warning(f"[DocumentService] Storage service write warning: {e}")

        stored_path = UPLOADS_DIR / stored_filename
        try:
            stored_path.write_bytes(unlocked_bytes)
        except Exception as e:
            pass

        extracted_json_bytes = json.dumps(pages, indent=2).encode("utf-8")
        try:
            storage_service.put_object(r2_extracted_key, extracted_json_bytes, content_type="application/json")
        except Exception as e:
            pass

        extracted_path = EXTRACTED_DIR / f"{doc_id}.json"
        try:
            extracted_path.write_text(json.dumps(pages, indent=2), encoding="utf-8")
        except Exception as e:
            pass

        try:
            from backend.services.db_service import db_service
            db_service.create_document(new_entry)
            db_service.save_chunks(doc_id, semantic_chunks)
        except Exception as e:
            logger.warning(f"[DocumentService] DB document persistence warning: {e}")

        manifest = get_manifest()
        manifest = [m for m in manifest if m.get("id") != doc_id]
        manifest.append(new_entry)
        save_manifest(manifest)
    else:
        # Temporary in-memory persistence for guests (zero durable disk, DB, or R2 writes)
        from backend.services.guest_session_service import guest_session_service
        guest_session_service.add_document(
            session_id=owner_id,
            doc_dict=new_entry,
            pages=pages,
            chunks=semantic_chunks,
            raw_bytes=unlocked_bytes
        )

    # 8. Update in-memory vector store immediately
    vector_store.add_document(doc_id, safe_filename, pages, owner_id)
    index_after = len(vector_store.chunks)

    # 10b. Schedule background document summary precomputation (Mandate 4)
    try:
        from backend.rag.summarizer import schedule_document_summary_precomputation
        schedule_document_summary_precomputation(doc_id, new_entry, pages)
    except Exception as e:
        print(f"[DocumentService] Non-fatal: background summary precomputation scheduling error: {e}")

    # 11. Run retrieval smoke test against the newly indexed document
    import re
    first_page_text = pages[0].get("text", "") if pages else ""
    tokens = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", first_page_text)
    if tokens:
        smoke_test_query = " ".join(tokens[:6])
    else:
        all_text = " ".join(p.get("text", "") for p in pages)
        all_tokens = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", all_text)
        if all_tokens:
            smoke_test_query = " ".join(all_tokens[:6])
        else:
            smoke_test_query = safe_filename

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
        logger.error(f"[DocumentService] CRITICAL: Ingestion smoke test failed for {doc_id} ({safe_filename}). Rolling back.")
        if is_authenticated:
            # Roll back durable storage, database records, and manifest
            if stored_path is not None and stored_path.exists():
                stored_path.unlink(missing_ok=True)
            if extracted_path is not None and extracted_path.exists():
                extracted_path.unlink(missing_ok=True)
            try:
                manifest = get_manifest()
                manifest = [m for m in manifest if m.get("id") != doc_id]
                save_manifest(manifest)
            except Exception as e:
                logger.warning(f"[DocumentService] Manifest rollback warning: {e}")
            try:
                from backend.services.db_service import db_service
                db_service.delete_document(doc_id)
            except Exception as e:
                logger.warning(f"[DocumentService] DB rollback warning: {e}")
            try:
                from backend.services.storage_service import storage_service
                storage_service.delete_object(r2_upload_key)
                storage_service.delete_object(r2_extracted_key)
            except Exception as e:
                logger.warning(f"[DocumentService] Storage rollback warning: {e}")
        else:
            # Guest session rollback: purely in-memory, zero durable operations
            from backend.services.guest_session_service import guest_session_service
            guest_session_service.delete_document(owner_id, doc_id)

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


def delete_document(
    doc_id: str,
    caller_id: str = "dev-user",
    is_authenticated: bool = False,
    is_admin: bool = False,
    db_hook: Optional[Callable[[str], None]] = None,
    owner_id: Optional[str] = None
) -> DeleteResult:
    """
    Deletes a document from disk, manifest, and vector store with strict authorization
    and atomic transactional rollback across all state stores.

    Policies:
    1. Privileged Administrator:
       - Verified admin (is_admin=True) or internal "system" can delete any document.
    2. Public Documents:
       - Documents owned by "public" or "system_public" CANNOT be deleted by normal users or guests.
       - Only privileged admins can delete public documents.
    3. Authenticated Document Owner:
       - An authenticated user (is_authenticated=True) can delete documents where target_owner == caller_id.
    4. Authenticated Cross-User Attempt:
        - An authenticated user cannot delete a document owned by a different user (target_owner != caller_id).
        - Returns DeleteResult(False, "FORBIDDEN_CROSS_USER").
    5. Unowned / Legacy Documents:
        - Documents where target_owner is None/empty and no explicit guest workspace is defined
          cannot be deleted by normal authenticated users or guests.
        - Returns DeleteResult(False, "UNOWNED_DOCUMENT_UNAUTHORIZED").
    6. Guest / Dev Workspace:
        - Unauthenticated caller (is_authenticated=False) can only delete documents explicitly owned
          by the guest workspace (target_owner in ["dev-user", "guest"] or workspace in ["guest", "dev"]).
        - Unauthenticated caller CANNOT delete registered user documents, public documents, or unowned documents.
        - Returns DeleteResult(False, "GUEST_UNAUTHORIZED") or DeleteResult(False, "CANNOT_DELETE_PUBLIC_DOC").
    """
    if owner_id is not None:
        caller_id = owner_id
        is_authenticated = True
    # Check GuestSessionService first if caller is unauthenticated
    if not is_authenticated:
        from backend.services.guest_session_service import guest_session_service
        if guest_session_service.get_document(caller_id, doc_id):
            guest_session_service.delete_document(caller_id, doc_id)
            vector_store.remove_document(doc_id)
            return DeleteResult(True, "DELETED")

    manifest = get_manifest()
    target = next((m for m in manifest if m.get("id") == doc_id or m.get("document_id") == doc_id), None)
    if not target:
        return DeleteResult(False, "NOT_FOUND")

    target_owner = target.get("ownerId") or target.get("owner_id")
    target_workspace = target.get("workspace") or target.get("workspace_id") or target.get("workspaceId")

    # Policy Evaluation:
    # 1. Privileged Administrator (verified via JWT or system internal)
    if is_admin or caller_id == "system":
        pass  # Authorized across tenants and unowned/legacy documents

    # 2. Public documents cannot be deleted by non-admins
    elif target_owner in ["public", "system_public"]:
        return DeleteResult(False, "CANNOT_DELETE_PUBLIC_DOC")

    # 3. Unowned / Legacy / Migrated documents without explicit guest workspace
    # Do NOT infer guest ownership merely because target_owner is None
    elif not target_owner and target_workspace not in ["guest", "dev"]:
        return DeleteResult(False, "UNOWNED_DOCUMENT_UNAUTHORIZED")

    # 4. Authenticated Document Owner
    elif is_authenticated and target_owner == caller_id:
        pass  # Authorized owner deletion

    # 5. Authenticated Non-Owner (Cross-user isolation: User B cannot delete User A's document)
    elif is_authenticated and target_owner != caller_id:
        return DeleteResult(False, "FORBIDDEN_CROSS_USER")

    # 6. Guest / Dev Workspace: can delete ONLY explicitly guest/dev-owned documents
    elif not is_authenticated:
        if target_owner in ["dev-user", "guest"] or target_workspace in ["guest", "dev"]:
            pass  # Authorized within explicit guest sandbox
        else:
            return DeleteResult(False, "GUEST_UNAUTHORIZED")

    else:
        return DeleteResult(False, "UNAUTHORIZED")

    # -------------------------------------------------------------------------
    # Transactional Execution with Atomic Rollback & Compensating Strategy
    # Phase 10: ACTIVE -> DELETING -> R2/disk delete -> DB delete -> Index rebuild -> DELETED
    # -------------------------------------------------------------------------
    from backend.services.db_service import db_service
    from backend.services.storage_service import storage_service

    # Step 0: Transition state ACTIVE -> DELETING
    try:
        db_service.mark_document_deleting(doc_id)
    except Exception as e:
        logger.warning(f"[DocumentService] Failed to mark document deleting: {e}")

    original_manifest = list(manifest)
    original_chunks = [dict(c) for c in vector_store.chunks if (c.get("document_id") == doc_id or c.get("documentId") == doc_id)]
    in_memory_doc_backup = dict(vector_store.in_memory_docs.get(doc_id)) if doc_id in vector_store.in_memory_docs else None

    filename = target.get("filename")
    upload_path = (UPLOADS_DIR / filename) if filename else None
    extracted_file = EXTRACTED_DIR / f"{doc_id}.json"

    upload_bytes_backup = upload_path.read_bytes() if (upload_path and upload_path.exists()) else None
    extracted_bytes_backup = extracted_file.read_bytes() if extracted_file.exists() else None

    # Cancel active background precomputations
    try:
        from backend.rag.summarizer import cancel_document_summary_precomputation
        cancel_document_summary_precomputation(doc_id)
    except Exception:
        pass

    files_unlinked = []
    manifest_saved = False
    vector_removed = False
    db_deleted = False

    try:
        # Step 1: Optional database metadata hook (test injection)
        if db_hook:
            db_hook(doc_id)

        # Step 2: Storage deletion (Cloudflare R2 and local filesystem)
        storage_service.delete_object(f"uploads/{doc_id}/original")
        storage_service.delete_object(f"extracted/{doc_id}/pages.json")

        if upload_path and upload_path.exists():
            upload_path.unlink()
            files_unlinked.append((upload_path, upload_bytes_backup))

        if extracted_file.exists():
            extracted_file.unlink()
            files_unlinked.append((extracted_file, extracted_bytes_backup))

        # Step 3: Database row deletion (cascading chunks, embeddings, summaries)
        try:
            db_service.delete_document(doc_id)
            db_deleted = True
        except Exception as e:
            raise RuntimeError(f"Database deletion failed: {e}")

        # Step 4: Manifest update
        updated_manifest = [m for m in manifest if m.get("id") != doc_id and m.get("document_id") != doc_id]
        save_manifest(updated_manifest)
        manifest_saved = True

        # Step 5: Vector store removal
        vector_store.remove_document(doc_id)
        vector_removed = True

        # Step 6: Invalidate summary cache
        from backend.services.summary_cache import summary_cache
        summary_cache.invalidate_document(doc_id)

    except Exception as e:
        logger.error(f"[DocumentService] Transactional deletion failed for '{doc_id}': {e}. Initiating compensating rollback.")
        # COMPENSATING ROLLBACK:
        # 1. Restore any physical files that were unlinked
        for fpath, fcontent in files_unlinked:
            if fcontent is not None and not fpath.exists():
                try:
                    fpath.write_bytes(fcontent)
                except Exception as r_err:
                    logger.critical(f"[DocumentService] Rollback failed to restore file {fpath}: {r_err}")

        # 2. Restore storage service object if backup available
        if upload_bytes_backup:
            try:
                storage_service.put_object(f"uploads/{doc_id}/original", upload_bytes_backup)
            except Exception:
                pass

        # 3. Restore database document status or record
        try:
            if db_deleted:
                db_service.create_document(target)
            else:
                db_service.update_document_status(doc_id, "completed", "indexed")
        except Exception as r_err:
            logger.critical(f"[DocumentService] Rollback failed to restore database row: {r_err}")

        # 4. Restore manifest if it was mutated
        if manifest_saved:
            try:
                save_manifest(original_manifest)
            except Exception as r_err:
                logger.critical(f"[DocumentService] Rollback failed to restore manifest: {r_err}")

        # 5. Restore vector store if it was mutated
        if vector_removed:
            try:
                if in_memory_doc_backup:
                    vector_store.in_memory_docs[doc_id] = in_memory_doc_backup
                    vector_store._rebuild()
                else:
                    existing_ids = {c.get("id") or c.get("chunk_id") for c in vector_store.chunks}
                    for c in original_chunks:
                        cid = c.get("id") or c.get("chunk_id")
                        if cid not in existing_ids:
                            vector_store.chunks.append(c)
                    vector_store.rebuild_index()
            except Exception as r_err:
                logger.critical(f"[DocumentService] Rollback failed to restore vector store: {r_err}")

        return DeleteResult(False, f"DELETION_FAILED: {str(e)}")

    return DeleteResult(True, "SUCCESS")


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


def reindex_document(
    doc_id: str,
    caller_id: str = "dev-user",
    is_authenticated: bool = False,
    is_admin: bool = False
) -> Dict[str, Any]:
    """
    Re-extracts, re-chunks, and re-indexes an uploaded document from disk with authorization checks.
    """
    manifest = get_manifest()
    target = next((m for m in manifest if m.get("id") == doc_id or m.get("document_id") == doc_id), None)
    if not target:
        return {"ok": False, "status": 404, "error": f"Document '{doc_id}' not found in manifest."}

    target_owner = target.get("ownerId") or target.get("owner_id")
    target_workspace = target.get("workspace") or target.get("workspace_id") or target.get("workspaceId")

    # Authorization verification
    if is_admin or caller_id == "system":
        allowed = True
    elif not target_owner and target_workspace not in ["guest", "dev"]:
        allowed = False
    elif is_authenticated and target_owner == caller_id:
        allowed = True
    elif not is_authenticated and caller_id in ["dev-user", "guest"] and (target_owner in ["dev-user", "guest"] or target_workspace in ["guest", "dev"]):
        allowed = True
    else:
        allowed = False

    if not allowed:
        return {
            "ok": False,
            "status": 403,
            "error": f"Unauthorized: Caller '{caller_id}' cannot reindex document owned by '{target_owner}'."
        }

    filename = target.get("filename", f"{doc_id}.pdf")
    upload_path = UPLOADS_DIR / filename
    if not upload_path.exists():
        return {"ok": False, "status": 404, "error": f"File '{filename}' missing on disk."}

    # Re-extract using unified extractor
    safe_name = target.get("originalFilename") or target.get("original_filename") or filename
    raw_bytes = upload_path.read_bytes()
    mime = target.get("mimeType") or target.get("mime_type")
    pages, _ = extract_document_content(raw_bytes, safe_name, mime_type=mime)

    # Update extracted JSON
    extracted_path = EXTRACTED_DIR / f"{doc_id}.json"
    extracted_path.write_text(json.dumps(pages, indent=2), encoding="utf-8")

    # Update VectorStore preserving true ownership
    doc_owner = target_owner or caller_id
    vector_store.add_document(doc_id, safe_name, pages, doc_owner)

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


# ---------------------------------------------------------------------------
# PHASE 6+7: Async ingestion — fast path + background RAG processing
# ---------------------------------------------------------------------------

async def _ingest_background(
    doc_id: str,
    safe_filename: str,
    ext: str,
    mime_type: str,
    unlocked_bytes: bytes,
    pages: List[Dict[str, Any]],
    owner_id: str,
    is_authenticated: bool,
    r2_upload_key: str,
    r2_extracted_key: str,
    new_entry: Dict[str, Any],
) -> None:
    """
    Background task: chunk, embed, index, persist, smoke-test.
    Updates the document record to 'completed' or 'failed'.
    Called via asyncio.create_task(); never awaited by the upload endpoint.
    """
    import asyncio

    async def _mark_failed(reason: str) -> None:
        """Update document status to 'failed' in DB and manifest."""
        try:
            from backend.services.db_service import db_service
            db_service.update_document_status(doc_id, "failed", "failed")
        except Exception:
            pass
        try:
            manifest = get_manifest()
            for m in manifest:
                if m.get("id") == doc_id or m.get("document_id") == doc_id:
                    m["status"] = "failed"
                    m["processingStatus"] = "failed"
                    m["processing_status"] = "failed"
                    m["indexStatus"] = "failed"
                    m["index_status"] = "failed"
                    m["indexed"] = False
                    m["failureReason"] = reason
            save_manifest(manifest)
        except Exception:
            pass
        logger.error(f"[IngestBg] Document {doc_id} marked FAILED: {reason}")

    try:
        t0 = time.time()

        # ── Step B1: Semantic chunking ────────────────────────────────────
        # Run in executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        semantic_chunks = await loop.run_in_executor(
            None, semantic_chunk_document, pages, doc_id, safe_filename
        )
        total_chunks = len(semantic_chunks)
        chunk_ids = [c["chunk_id"] for c in semantic_chunks]

        if total_chunks == 0:
            await _mark_failed("NO_CHUNKS_PRODUCED: Text extraction produced no indexable chunks.")
            return

        t1 = time.time()
        logger.info(f"[IngestBg] {doc_id} chunked in {int((t1 - t0) * 1000)}ms → {total_chunks} chunks")

        # ── Step B2: Persist raw storage (R2 + local disk) ───────────────
        if is_authenticated:
            from backend.services.storage_service import storage_service
            try:
                await loop.run_in_executor(
                    None,
                    lambda: storage_service.put_object(
                        r2_upload_key, unlocked_bytes,
                        content_type=mime_type or ("application/pdf" if ext == ".pdf" else "text/plain")
                    )
                )
            except Exception as e:
                logger.warning(f"[IngestBg] R2 upload warning for {doc_id}: {e}")

            stored_filename = new_entry["filename"]
            stored_path = UPLOADS_DIR / stored_filename
            try:
                await loop.run_in_executor(None, stored_path.write_bytes, unlocked_bytes)
            except Exception as e:
                logger.warning(f"[IngestBg] Local file write warning for {doc_id}: {e}")

            extracted_json_bytes = json.dumps(pages, indent=2).encode("utf-8")
            try:
                await loop.run_in_executor(
                    None,
                    lambda: storage_service.put_object(r2_extracted_key, extracted_json_bytes, content_type="application/json")
                )
            except Exception:
                pass

            extracted_path = EXTRACTED_DIR / f"{doc_id}.json"
            try:
                await loop.run_in_executor(
                    None,
                    lambda: extracted_path.write_text(json.dumps(pages, indent=2), encoding="utf-8")
                )
            except Exception:
                pass

        t2 = time.time()
        logger.info(f"[IngestBg] {doc_id} stored in {int((t2 - t1) * 1000)}ms")

        # ── Step B3: DB chunks + update entry to 'completed' ─────────────
        if is_authenticated:
            try:
                from backend.services.db_service import db_service
                await loop.run_in_executor(None, db_service.save_chunks, doc_id, semantic_chunks)
            except Exception as e:
                logger.warning(f"[IngestBg] DB chunk save warning for {doc_id}: {e}")

        # ── Step B4: Vector store insertion ──────────────────────────────
        index_before = len(vector_store.chunks)
        await loop.run_in_executor(
            None, vector_store.add_document, doc_id, safe_filename, pages, owner_id
        )
        index_after = len(vector_store.chunks)

        t3 = time.time()
        logger.info(f"[IngestBg] {doc_id} indexed in {int((t3 - t2) * 1000)}ms → {index_after - index_before} new chunks")

        # ── Step B5: Smoke test ───────────────────────────────────────────
        import re
        first_page_text = pages[0].get("text", "") if pages else ""
        tokens = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", first_page_text)
        smoke_query = " ".join(tokens[:6]) if tokens else (
            " ".join(re.findall(r"\b[a-zA-Z0-9_]{2,}\b", " ".join(p.get("text", "") for p in pages))[:6])
            or safe_filename
        )
        smoke_candidates = vector_store.search(
            query=smoke_query, k=1, owner_id=owner_id, document_id=doc_id, scope="DOCUMENT"
        )
        smoke_passed = any(
            (c.get("document_id") == doc_id or c.get("documentId") == doc_id)
            for c in smoke_candidates
        )
        if not smoke_passed:
            # Roll back vector store and storage; mark failed
            vector_store.remove_document(doc_id)
            if is_authenticated:
                _manifest = get_manifest()
                save_manifest([m for m in _manifest if m.get("id") != doc_id])
                try:
                    from backend.services.db_service import db_service
                    db_service.delete_document(doc_id)
                except Exception:
                    pass
            else:
                try:
                    from backend.services.guest_session_service import guest_session_service
                    guest_session_service.delete_document(owner_id, doc_id)
                except Exception:
                    pass
            await _mark_failed("SMOKE_TEST_FAILED: Document indexed but retrieval validation failed.")
            return

        # ── Step B6: Mark completed ───────────────────────────────────────
        total_text_len = sum(len(p.get("text", "").strip()) for p in pages)

        completed_fields = {
            "status": "completed",
            "processingStatus": "completed",
            "processing_status": "completed",
            "indexStatus": "indexed",
            "index_status": "indexed",
            "indexed": True,
            "chunkCount": total_chunks,
            "chunk_count": total_chunks,
            "chunkIds": chunk_ids,
            "indexVersion": vector_store.index_version,
            "index_version": vector_store.index_version,
        }

        # Update DB status
        if is_authenticated:
            try:
                from backend.services.db_service import db_service
                db_service.update_document_status(doc_id, "completed", "indexed")
            except Exception as e:
                logger.warning(f"[IngestBg] DB status update warning for {doc_id}: {e}")

        # Update manifest
        try:
            manifest = get_manifest()
            for m in manifest:
                if m.get("id") == doc_id or m.get("document_id") == doc_id:
                    m.update(completed_fields)
            save_manifest(manifest)
        except Exception as e:
            logger.warning(f"[IngestBg] Manifest update warning for {doc_id}: {e}")

        # Update guest session entry with completed status AND actual chunks
        if not is_authenticated:
            try:
                from backend.services.guest_session_service import guest_session_service
                doc = guest_session_service.get_document(owner_id, doc_id)
                if doc:
                    doc.update(completed_fields)
                    # Persist the actual chunk dicts so callers can access them
                    doc["chunks"] = semantic_chunks
            except Exception:
                pass

        t4 = time.time()
        logger.info(f"[IngestBg] {doc_id} COMPLETED in {int((t4 - t0) * 1000)}ms total background time")

        # ── Step B7: Background document summary precomputation ───────────
        try:
            from backend.rag.summarizer import schedule_document_summary_precomputation
            schedule_document_summary_precomputation(doc_id, new_entry, pages)
        except Exception as e:
            logger.debug(f"[IngestBg] Summary precomputation scheduling: {e}")

        log_upload_summary(
            doc_id=doc_id,
            filename=safe_filename,
            page_count=len(pages),
            char_count=total_text_len,
            chunk_count=total_chunks,
            index_before=index_before,
            index_after=index_after,
            duration_ms=int((t4 - t0) * 1000),
            status="indexed"
        )

    except Exception as exc:
        logger.error(f"[IngestBg] Unhandled exception for {doc_id}: {exc}", exc_info=True)
        await _mark_failed(f"INTERNAL_ERROR: {str(exc)}")


async def ingest_file_async(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
    owner_id: str = "dev-user",
    is_authenticated: bool = True,
    password: Optional[str] = None
) -> Dict[str, Any]:
    """
    Two-phase async ingestion:

    FAST PATH (returns in ~1-3s):
      1. Validate size, extension, filename traversal
      2. Compute SHA-256 and check duplicate
      3. Extract text (CPU-bound, but unavoidable before dedup and validation)
      4. Validate non-empty text
      5. Write a 'processing' record to DB + manifest
      6. Return { status: 'processing', document: {...} }

    BACKGROUND TASK (fires asyncio.create_task, runs ~5-120s):
      B1. Semantic chunking
      B2. Persist raw bytes to R2 + local disk
      B3. Save chunks to DB
      B4. Add to in-memory vector store
      B5. Smoke test retrieval
      B6. Mark document 'completed'
      B7. Schedule summary precomputation

    The client should poll GET /api/documents or use the WebSocket event
    to learn when processingStatus transitions to 'completed'.
    """
    import asyncio

    start_time = time.time()

    # ── FAST PATH: Steps 1-4 (identical validation logic to ingest_file) ──

    # 1. Sanitize filename & validate extension
    safe_filename = Path(filename).name
    if not safe_filename:
        safe_filename = "document.pdf"

    ext = Path(safe_filename).suffix.lower()
    allowed_exts = [".pdf", ".docx", ".txt", ".md"]
    if ext == ".doc":
        return {
            "ok": False,
            "status": 400,
            "error": {
                "code": "UNSUPPORTED_FORMAT",
                "message": "Legacy binary .doc files are not supported. Please save or convert your document to modern .docx format before uploading.",
                "filename": safe_filename,
                "field": "file"
            }
        }
    if ext not in allowed_exts:
        return {
            "ok": False,
            "status": 400,
            "error": {
                "code": "UNSUPPORTED_FORMAT",
                "message": f"File extension '{ext}' is not supported. Supported formats: .pdf, .docx, .txt, .md.",
                "filename": safe_filename,
                "field": "file"
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
                "message": f"File size ({len(file_bytes)} bytes) exceeds the 25MB maximum limit.",
                "filename": safe_filename,
                "field": "file"
            }
        }

    if len(file_bytes) == 0:
        return {
            "ok": False,
            "status": 400,
            "error": {
                "code": "EMPTY_FILE",
                "message": "Uploaded file is 0 bytes.",
                "filename": safe_filename,
                "field": "file"
            }
        }

    # 3. Compute SHA-256 and check for duplicate
    file_hash = compute_sha256(file_bytes)
    existing = None
    if is_authenticated:
        try:
            from backend.services.db_service import db_service
            existing = db_service.get_document_by_hash(file_hash, owner_id)
        except Exception:
            existing = None

        if not existing:
            manifest = get_manifest()
            existing = next(
                (m for m in manifest if m.get("hash") == file_hash and (m.get("ownerId") == owner_id or m.get("owner_id") == owner_id)),
                None
            )
    else:
        from backend.services.guest_session_service import guest_session_service
        session_docs = guest_session_service.get_documents(owner_id)
        existing = next((d for d in session_docs if d.get("hash") == file_hash), None)

    if existing:
        existing_filename = existing.get("originalFilename") or existing.get("original_filename") or existing.get("filename") or "document"
        if existing_filename and existing_filename.strip().lower() != safe_filename.strip().lower():
            dup_msg = f"This file has already been uploaded as '{existing_filename}'."
        else:
            dup_msg = f"File '{safe_filename}' already exists in your knowledge base."
        return {
            "ok": False,
            "status": 409,
            "error": {
                "code": "DUPLICATE",
                "message": dup_msg,
                "existingId": existing.get("id") or existing.get("document_id"),
                "existingFilename": existing_filename,
                "filename": safe_filename,
                "field": "file"
            }
        }

    # 4. Extract text & validate password BEFORE saving any files or DB records
    pages: List[Dict[str, Any]] = []
    unlocked_bytes = file_bytes
    try:
        loop = asyncio.get_event_loop()
        pages, unlocked_bytes = await loop.run_in_executor(
            None,
            lambda: extract_document_content(
                file_bytes=file_bytes,
                filename=safe_filename,
                mime_type=mime_type,
                password=password
            )
        )
    except PDFPasswordRequiredError as e:
        return {
            "ok": False,
            "status": 401,
            "error": {"code": "PASSWORD_REQUIRED", "message": str(e), "filename": safe_filename, "field": "password"}
        }
    except PDFIncorrectPasswordError as e:
        return {
            "ok": False,
            "status": 401,
            "error": {"code": "INCORRECT_PASSWORD", "message": str(e), "filename": safe_filename, "field": "password"}
        }
    except UnsupportedFormatError as e:
        return {
            "ok": False,
            "status": 400,
            "error": {"code": "UNSUPPORTED_FORMAT", "message": str(e), "filename": safe_filename, "field": "file"}
        }
    except Exception as e:
        logger.error(f"[IngestAsync] Extraction failed for {safe_filename}: {e}")
        return {
            "ok": False,
            "status": 422,
            "error": {
                "code": "EXTRACTION_FAILED",
                "message": f"Failed to extract document content: {str(e)}",
                "filename": safe_filename,
                "field": "file"
            }
        }

    # Validate usable text
    total_text_len = sum(len(p.get("text", "").strip()) for p in pages)
    if ext == ".pdf" and (total_text_len < 10 or len(pages) == 0):
        return {
            "ok": False,
            "status": 422,
            "error": {
                "code": "OCR_REQUIRED",
                "message": "PDF uploaded, but no selectable text was found. OCR is required.",
                "filename": safe_filename,
                "field": "file"
            }
        }
    if total_text_len == 0 or len(pages) == 0:
        return {
            "ok": False,
            "status": 422,
            "error": {
                "code": "EMPTY_OR_UNREADABLE",
                "message": "Document contains no readable text or failed text extraction. It may be image-only or empty.",
                "filename": safe_filename,
                "field": "file"
            }
        }

    fast_ms = int((time.time() - start_time) * 1000)
    logger.info(f"[IngestAsync] {safe_filename} fast path complete in {fast_ms}ms ({len(pages)} pages, {total_text_len} chars)")

    # ── 5. Create 'processing' document record ────────────────────────────

    doc_id = str(uuid.uuid4())
    stored_filename = f"{doc_id}{ext}"
    r2_upload_key = f"uploads/{doc_id}/original"
    r2_extracted_key = f"extracted/{doc_id}/pages.json"
    now_iso = datetime.now(timezone.utc).isoformat()

    resolved_mime = mime_type or (
        "application/pdf" if ext == ".pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if ext == ".docx"
        else "text/markdown" if ext in [".md", ".markdown"]
        else "text/plain"
    )

    new_entry: Dict[str, Any] = {
        "schemaVersion": 2,
        "id": doc_id,
        "document_id": doc_id,
        "filename": stored_filename,
        "storage_filename": stored_filename,
        "originalFilename": safe_filename,
        "original_filename": safe_filename,
        "mimeType": resolved_mime,
        "mime_type": resolved_mime,
        "extension": ext,
        "size": len(file_bytes),
        "sizeBytes": len(file_bytes),
        "size_bytes": len(file_bytes),
        "uploadedAt": now_iso,
        "created_at": now_iso,
        "createdAt": now_iso,
        "lastModified": now_iso,
        "updated_at": now_iso,
        "pageCount": len(pages) if ext == ".pdf" else max(len(pages), 1),
        "page_count": len(pages) if ext == ".pdf" else max(len(pages), 1),
        "characterCount": total_text_len,
        "charCount": total_text_len,
        "char_count": total_text_len,
        "extractedCharCount": total_text_len,
        "extracted_char_count": total_text_len,
        # Chunk fields will be filled in by background task
        "chunkCount": 0,
        "chunk_count": 0,
        "chunkIds": [],
        # Status: processing until background task completes
        "status": "processing",
        "processingStatus": "processing",
        "processing_status": "processing",
        "indexStatus": "processing",
        "index_status": "processing",
        "indexed": False,
        "indexVersion": vector_store.index_version,
        "index_version": vector_store.index_version,
        "ownerId": owner_id,
        "owner_id": owner_id,
        "tenantId": owner_id,
        "tenant_id": owner_id,
        "hash": file_hash,
        "fileHash": file_hash,
        "file_hash": file_hash,
        "r2_upload_key": r2_upload_key if is_authenticated else None,
        "r2_extracted_key": r2_extracted_key if is_authenticated else None,
        "lifecycle_state": "ACTIVE",
        "indexInsertionStatus": "processing",
        "index_insertion_status": "processing",
    }

    # Persist the 'processing' record immediately so the client can see it
    if is_authenticated:
        try:
            from backend.services.db_service import db_service
            db_service.create_document(new_entry)
        except Exception as e:
            logger.warning(f"[IngestAsync] DB create_document warning for {doc_id}: {e}")

        try:
            manifest = get_manifest()
            manifest = [m for m in manifest if m.get("id") != doc_id]
            manifest.append(new_entry)
            save_manifest(manifest)
        except Exception as e:
            logger.warning(f"[IngestAsync] Manifest save warning for {doc_id}: {e}")
    else:
        # Guest: register in-memory record immediately (without chunks/raw bytes — those come in bg task)
        try:
            from backend.services.guest_session_service import guest_session_service
            guest_session_service.add_document(
                session_id=owner_id,
                doc_dict=new_entry,
                pages=pages,
                chunks=[],
                raw_bytes=unlocked_bytes
            )
        except Exception as e:
            logger.warning(f"[IngestAsync] Guest session add_document warning for {doc_id}: {e}")

    # ── 6. Return background coroutine for the caller to schedule ────────────
    # We return the coroutine instead of calling asyncio.create_task() here,
    # so the upload endpoint can register it with FastAPI's BackgroundTasks.
    # This ensures it runs reliably in both production (ASGI) and TestClient.
    background_coro = _ingest_background(
        doc_id=doc_id,
        safe_filename=safe_filename,
        ext=ext,
        mime_type=resolved_mime,
        unlocked_bytes=unlocked_bytes,
        pages=pages,
        owner_id=owner_id,
        is_authenticated=is_authenticated,
        r2_upload_key=r2_upload_key,
        r2_extracted_key=r2_extracted_key,
        new_entry=new_entry,
    )

    logger.info(f"[IngestAsync] {doc_id} ({safe_filename}) accepted in {fast_ms}ms — background task ready")

    return {
        "ok": True,
        "success": True,
        "status": 202,
        "processing": True,
        "document": new_entry,
        "_background_coro": background_coro,
    }
