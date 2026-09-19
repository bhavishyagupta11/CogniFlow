"""
Document Management Router
Handles listing, file ingestion (PyMuPDF), document deletion, and PDF serving.
"""

from typing import List, Optional, Union
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, UploadFile, File, Form, Response, Request, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from backend.config import UPLOADS_DIR, EXTRACTED_DIR
from backend.services.document_service import get_manifest, ingest_file, ingest_file_async, delete_document, reindex_document, inspect_document
from backend.services.auth_service import resolve_caller_identity, get_optional_user
from backend.rag.vector_store import vector_store

router = APIRouter(tags=["documents"])


def _run_coro(coro) -> None:
    """
    Sync wrapper that runs an async coroutine to completion.
    Used as the BackgroundTasks callable since FastAPI runs background tasks
    in a threadpool executor (not in the event loop), so we need asyncio.run().
    """
    import asyncio
    asyncio.run(coro)



@router.get("/api/documents")
async def list_documents(
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    identity = await resolve_caller_identity(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if identity.session_id:
        response.headers["X-Session-ID"] = identity.session_id

    manifest = get_manifest()
    
    # 1. Privileged admin sees all documents
    if identity.is_admin:
        return [
            dict(m,
                 ownerId=m.get("ownerId") or m.get("owner_id") or identity.user_id,
                 owner_id=m.get("owner_id") or m.get("ownerId") or identity.user_id,
                 indexStatus=m.get("indexStatus", "indexed"))
            for m in manifest
        ]

    # 2. Authenticated user sees only their own documents
    if identity.is_authenticated:
        return [
            dict(m,
                 ownerId=m.get("ownerId") or m.get("owner_id"),
                 owner_id=m.get("owner_id") or m.get("ownerId"),
                 indexStatus=m.get("indexStatus", "indexed"))
            for m in manifest
            if (m.get("ownerId") == identity.user_id or m.get("owner_id") == identity.user_id)
        ]

    # 3. Guest session sees only temporary documents uploaded in this active session
    from backend.services.guest_session_service import guest_session_service
    guest_docs = guest_session_service.get_documents(identity.user_id)
    # If backward-compatible dev-user test session
    if identity.user_id in ["guest_dev-user", "dev-user"]:
        legacy_dev_docs = [
            dict(m, ownerId=m.get("ownerId") or m.get("owner_id"), indexStatus=m.get("indexStatus", "indexed"))
            for m in manifest
            if m.get("ownerId") in ["dev-user", "guest"] or m.get("owner_id") in ["dev-user", "guest"]
        ]
        return guest_docs + legacy_dev_docs

    return guest_docs


@router.get("/api/documents/{doc_id}")
async def get_document_by_id(
    doc_id: str,
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """Retrieves metadata for a single document, enforcing tenant/session isolation."""
    from backend.services.db_service import db_service
    from backend.services.guest_session_service import guest_session_service

    identity = await resolve_caller_identity(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if identity.session_id:
        response.headers["X-Session-ID"] = identity.session_id

    # 1. Check guest session
    guest_doc = guest_session_service.get_document(identity.user_id, doc_id)
    if guest_doc:
        d = dict(guest_doc)
        d.pop("raw_bytes", None)
        return d

    # 2. Check persistent DB / manifest
    target = db_service.get_document(doc_id)
    if not target:
        manifest = get_manifest()
        target = next((m for m in manifest if m.get("id") == doc_id or m.get("document_id") == doc_id), None)
        if not target:
            raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

    target_owner = target.get("ownerId") or target.get("owner_id")
    target_workspace = target.get("workspace") or target.get("workspace_id")

    if identity.is_admin or identity.user_id == "system":
        allowed = True
    elif target_owner in ["public", "system_public"]:
        allowed = True
    elif identity.is_authenticated:
        allowed = (target_owner == identity.user_id)
    else:
        allowed = (target_owner in ["dev-user", "guest", "user_default"] or target_workspace in ["guest", "dev"])

    if not allowed:
        raise HTTPException(status_code=403, detail=f"Forbidden: Not authorized to access document '{doc_id}'")

    return target


@router.post("/api/documents")
@router.post("/api/documents/upload")
async def upload_documents(
    response: Response,
    background_tasks: BackgroundTasks,
    file: Union[UploadFile, List[UploadFile]] = File(...),
    password: Optional[str] = Form(None),
    x_document_password: Optional[str] = Header(None),
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    identity = await resolve_caller_identity(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if identity.session_id:
        response.headers["X-Session-ID"] = identity.session_id

    file_list = file if isinstance(file, list) else [file]
    if not file_list:
        return JSONResponse(
            status_code=400,
            content={
                "ok": False,
                "error": {
                    "code": "NO_FILE_PROVIDED",
                    "message": "No files were included in the upload request."
                }
            }
        )

    doc_password = (password.strip() if password else None) or (x_document_password.strip() if x_document_password else None)

    results = []
    for f in file_list:
        try:
            content = await f.read()
            res = await ingest_file_async(
                file_bytes=content,
                filename=f.filename or "uploaded_file.pdf",
                mime_type=f.content_type or "application/pdf",
                owner_id=identity.user_id,
                is_authenticated=identity.is_authenticated,
                password=doc_password
            )
            # Register background coroutine with FastAPI BackgroundTasks
            # (runs after response is sent; works in both ASGI and TestClient)
            if res.get("ok") and "_background_coro" in res:
                background_tasks.add_task(_run_coro, res.pop("_background_coro"))
            elif "_background_coro" in res:
                # discard unawaited coroutine to avoid RuntimeWarning
                res.pop("_background_coro").close()
            results.append(res)
        except Exception as e:
            results.append({
                "ok": False,
                "status": 500,
                "error": {
                    "code": "INGESTION_ERROR",
                    "message": f"Unexpected error ingesting {f.filename}: {str(e)}"
                }
            })

    # If single file upload
    def sanitize_doc(d):
        if not isinstance(d, dict):
            return d
        c = dict(d)
        c.pop("raw_bytes", None)
        return c

    sanitized_results = []
    for r in results:
        sr = dict(r)
        if "document" in sr and isinstance(sr["document"], dict):
            sr["document"] = sanitize_doc(sr["document"])
        sanitized_results.append(sr)
    results = sanitized_results

    if len(file_list) == 1:
        first = results[0]
        if not first.get("ok"):
            status_code = first.get("status", 400)
            return JSONResponse(
                status_code=status_code,
                headers={"X-Session-ID": identity.session_id} if identity.session_id else None,
                content={
                    "ok": False,
                    "error": first.get("error", {"code": "UPLOAD_FAILED", "message": "Upload failed."}),
                    "results": results
                }
            )

        doc = first.get("document", {})
        # Return 202 Accepted when document is queued for background processing
        http_status = 202 if first.get("processing") else 200
        return JSONResponse(
            status_code=http_status,
            headers={"X-Session-ID": identity.session_id} if identity.session_id else None,
            content={
                "ok": True,
                "processing": first.get("processing", False),
                "document": doc,
                "results": results
            }
        )

    # Multi-file upload
    all_ok = all(r.get("ok") for r in results)
    successful_docs = [r["document"] for r in results if r.get("ok") and "document" in r]
    
    return JSONResponse(
        status_code=200 if all_ok else 207,
        headers={"X-Session-ID": identity.session_id} if identity.session_id else None,
        content={
            "ok": all_ok,
            "document": successful_docs[0] if successful_docs else None,
            "documents": successful_docs,
            "results": results
        }
    )


@router.delete("/api/documents/{doc_id}")
async def remove_document(
    doc_id: str,
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    identity = await resolve_caller_identity(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if identity.session_id:
        response.headers["X-Session-ID"] = identity.session_id

    success, reason = delete_document(
        doc_id=doc_id,
        caller_id=identity.user_id,
        is_authenticated=identity.is_authenticated,
        is_admin=identity.is_admin
    )
    if not success:
        if reason == "NOT_FOUND":
            return JSONResponse(
                status_code=404,
                content={
                    "ok": False,
                    "error": {
                        "code": "NOT_FOUND",
                        "message": f"Document '{doc_id}' not found."
                    }
                }
            )
        elif reason in ["FORBIDDEN_CROSS_USER", "GUEST_UNAUTHORIZED", "UNOWNED_DOCUMENT_UNAUTHORIZED"]:
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": f"Unauthorized: Caller '{identity.user_id}' cannot delete this document."
                    }
                }
            )
        elif reason == "CANNOT_DELETE_PUBLIC_DOC":
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "Public and system documents cannot be deleted by non-admin callers."
                    }
                }
            )
        elif reason.startswith("DELETION_FAILED"):
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "error": {
                        "code": "DELETION_FAILED",
                        "message": f"Document deletion failed and was safely rolled back: {reason}"
                    }
                }
            )
        else:
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": f"Deletion unauthorized: {reason}"
                    }
                }
            )

    return {"ok": True, "id": doc_id, "message": "Document deleted successfully"}


def create_byte_range_response(
    content_bytes: bytes,
    media_type: str,
    safe_filename: str,
    range_header: Optional[str] = None,
    session_id: Optional[str] = None,
    is_guest: bool = False
) -> Response:
    """
    Constructs an RFC 7233 compliant byte response supporting:
    - Normal 200 OK with full content and Content-Length
    - Range requests (bytes=start-end) returning 206 Partial Content and Content-Range
    - Safe handling of out-of-bounds ranges returning 416 Range Not Satisfiable
    - Strict non-conditional headers for guest in-memory documents to prevent 304 Not Modified
    """
    total_len = len(content_bytes)

    if is_guest:
        cache_control = "no-store, no-cache, must-revalidate, max-age=0"
    else:
        cache_control = "private, no-transform, max-age=300"

    common_headers = {
        "Content-Disposition": f'inline; filename="{safe_filename}"',
        "Accept-Ranges": "bytes",
        "Cache-Control": cache_control,
    }
    if is_guest:
        common_headers["Pragma"] = "no-cache"
        common_headers["Expires"] = "0"

    if session_id:
        common_headers["X-Session-ID"] = session_id

    if not range_header or not range_header.startswith("bytes="):
        # Full content response
        resp_headers = dict(common_headers)
        resp_headers["Content-Length"] = str(total_len)
        return Response(
            content=content_bytes,
            status_code=200,
            media_type=media_type,
            headers=resp_headers
        )

    # Parse Range: bytes=start-end
    range_spec = range_header.strip()[6:].strip()
    if "," in range_spec:
        range_spec = range_spec.split(",")[0].strip()

    parts = range_spec.split("-", 1)
    start_str, end_str = parts[0].strip(), parts[1].strip()

    try:
        if start_str and end_str:
            start = int(start_str)
            end = int(end_str)
        elif start_str and not end_str:
            start = int(start_str)
            end = total_len - 1
        elif not start_str and end_str:
            suffix_len = int(end_str)
            start = max(0, total_len - suffix_len)
            end = total_len - 1
        else:
            raise ValueError("Invalid range specification")
    except ValueError:
        err_headers = dict(common_headers)
        err_headers["Content-Range"] = f"bytes */{total_len}"
        return Response(
            status_code=416,
            headers=err_headers
        )

    if start < 0 or start >= total_len or end < start:
        err_headers = dict(common_headers)
        err_headers["Content-Range"] = f"bytes */{total_len}"
        return Response(
            status_code=416,
            headers=err_headers
        )

    end = min(end, total_len - 1)
    chunk_len = end - start + 1
    slice_data = content_bytes[start : end + 1]

    resp_headers = dict(common_headers)
    resp_headers["Content-Range"] = f"bytes {start}-{end}/{total_len}"
    resp_headers["Content-Length"] = str(chunk_len)

    return Response(
        content=slice_data,
        status_code=206,
        media_type=media_type,
        headers=resp_headers
    )


@router.get("/api/documents/{doc_id}/pdf")
@router.get("/api/documents/{doc_id}/raw")
async def view_document_pdf(
    doc_id: str,
    request: Request,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None)
):
    from backend.services.db_service import db_service
    from backend.services.storage_service import storage_service, R2StorageService
    from backend.services.guest_session_service import guest_session_service

    effective_auth = authorization or (f"Bearer {token.strip()}" if token and token.strip() else None)
    effective_session = x_session_id or (session_id.strip() if session_id and session_id.strip() else None)
    range_header = request.headers.get("Range")

    # 1. Authoritatively resolve caller identity
    identity = await resolve_caller_identity(
        authorization=effective_auth,
        x_user_id=x_user_id,
        x_session_id=effective_session,
        request=request
    )

    # 2. Check guest in-memory documents first (temporary guest session state)
    guest_doc = guest_session_service.get_document(identity.user_id, doc_id)
    if guest_doc:
        target_owner = guest_doc.get("ownerId") or guest_doc.get("owner_id")
        if target_owner != identity.user_id:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Caller '{identity.user_id}' is not authorized to access document '{doc_id}'"
            )
        raw_bytes = guest_doc.get("raw_bytes")
        if not raw_bytes:
            raise HTTPException(status_code=404, detail="Binary document object not found in guest session")

        safe_filename = guest_doc.get("originalFilename") or guest_doc.get("original_filename") or f"{doc_id}.pdf"
        media_type = guest_doc.get("mimeType") or guest_doc.get("mime_type") or "application/pdf"
        if not media_type or media_type == "application/octet-stream":
            media_type = "application/pdf" if safe_filename.endswith(".pdf") else "text/plain"

        # Return actual PDF bytes directly with Range support (never written to R2, never cached with 304)
        return create_byte_range_response(
            content_bytes=raw_bytes,
            media_type=media_type,
            safe_filename=safe_filename,
            range_header=range_header,
            session_id=identity.session_id,
            is_guest=True
        )

    # If not found in caller's session, check if it belongs to ANY other active guest session
    other_guest_doc = guest_session_service.find_document_any_session(doc_id)
    if other_guest_doc:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Caller '{identity.user_id}' is not authorized to access document '{doc_id}'"
        )

    # 3. Check persistent database and manifest for authenticated/durable documents
    target = db_service.get_document(doc_id)
    if not target:
        manifest = get_manifest()
        target = next((m for m in manifest if m.get("id") == doc_id or m.get("document_id") == doc_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Document not found")

    target_owner = target.get("ownerId") or target.get("owner_id")
    target_workspace = target.get("workspace") or target.get("workspace_id") or target.get("workspaceId")

    # Authorization policy for persistent documents
    if identity.is_admin or identity.user_id == "system":
        allowed = True
    elif target_owner in ["public", "system_public"]:
        allowed = True
    elif identity.is_authenticated:
        allowed = (target_owner == identity.user_id)
    else:
        # Unauthenticated / guest workspace callers are strictly forbidden from accessing another user's documents
        allowed = (target_owner in ["dev-user", "guest", "user_default"] or target_workspace in ["guest", "dev"])

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Caller '{identity.user_id}' is not authorized to access document '{doc_id}'"
        )

    safe_filename = target.get("originalFilename") or target.get("original_filename") or f"{doc_id}.pdf"
    media_type = target.get("mimeType") or target.get("mime_type")
    if not media_type or media_type == "application/octet-stream":
        ext = Path(safe_filename).suffix.lower()
        if ext == ".pdf":
            media_type = "application/pdf"
        elif ext == ".docx":
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ext in [".md", ".markdown"]:
            media_type = "text/markdown; charset=utf-8"
        else:
            media_type = "text/plain; charset=utf-8"

    r2_upload_key = target.get("r2_upload_key") or f"uploads/{doc_id}/original"
    filename = target.get("filename") or f"{doc_id}.pdf"

    # 4. Cloudflare R2 short-lived signed URL for authenticated persistent storage
    if isinstance(storage_service, R2StorageService):
        try:
            presigned_url = storage_service.generate_presigned_url(r2_upload_key, expires_in_seconds=300)
            return RedirectResponse(url=presigned_url, status_code=307)
        except Exception as e:
            pass

    # 5. Object storage stream
    try:
        if storage_service.exists(r2_upload_key):
            content = storage_service.get_object(r2_upload_key)
            return create_byte_range_response(
                content_bytes=content,
                media_type=media_type,
                safe_filename=safe_filename,
                range_header=range_header,
                session_id=identity.session_id
            )
    except Exception:
        pass

    # 6. Local filesystem fallback
    ext_suffix = Path(safe_filename).suffix.lower()
    candidate_paths = [
        UPLOADS_DIR / Path(filename).name,
        UPLOADS_DIR / f"{doc_id}{ext_suffix}",
        UPLOADS_DIR / f"{doc_id}.pdf",
        UPLOADS_DIR / safe_filename
    ]
    for c_path in candidate_paths:
        try:
            resolved = c_path.resolve()
            if resolved.is_relative_to(UPLOADS_DIR.resolve()) and resolved.exists():
                content = resolved.read_bytes()
                return create_byte_range_response(
                    content_bytes=content,
                    media_type=media_type,
                    safe_filename=safe_filename,
                    range_header=range_header,
                    session_id=identity.session_id
                )
        except Exception:
            continue

    raise HTTPException(status_code=404, detail="Binary document object not found in storage")


@router.post("/api/documents/{doc_id}/reindex")
async def reindex_single_document(
    doc_id: str,
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    identity = await resolve_caller_identity(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if identity.session_id:
        response.headers["X-Session-ID"] = identity.session_id
    res = reindex_document(
        doc_id=doc_id,
        caller_id=identity.user_id,
        is_authenticated=identity.is_authenticated,
        is_admin=identity.is_admin
    )
    status_code = res.get("status", 200)
    return JSONResponse(status_code=status_code, content=res)


@router.get("/api/documents/{doc_id}/content")
async def get_document_content(
    doc_id: str,
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """Returns normalized extracted sections and full text for in-app viewing (PDF, DOCX, TXT, MD)."""
    import json
    from backend.services.db_service import db_service
    from backend.services.guest_session_service import guest_session_service

    identity = await resolve_caller_identity(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if identity.session_id:
        response.headers["X-Session-ID"] = identity.session_id

    # 1. Guest session documents
    guest_doc = guest_session_service.get_document(identity.user_id, doc_id)
    if guest_doc:
        pages = guest_session_service.get_document_pages(identity.user_id, doc_id) or []
        orig_name = guest_doc.get("originalFilename") or guest_doc.get("original_filename") or doc_id
        mime = guest_doc.get("mimeType") or guest_doc.get("mime_type") or "text/plain"
        ext = Path(orig_name).suffix.lower().lstrip(".")
        fmt = "pdf" if ext == "pdf" else ("docx" if ext == "docx" else ("md" if ext in ["md", "markdown"] else "txt"))
        return {
            "id": doc_id,
            "document_id": doc_id,
            "originalFilename": orig_name,
            "mimeType": mime,
            "format": fmt,
            "sections": pages,
            "text": "\n\n".join(p.get("text", "") for p in pages)
        }

    # 2. Persistent documents
    target = db_service.get_document(doc_id)
    if not target:
        manifest = get_manifest()
        target = next((m for m in manifest if m.get("id") == doc_id or m.get("document_id") == doc_id), None)
        if not target:
            raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

    target_owner = target.get("ownerId") or target.get("owner_id")
    if not (
        identity.is_admin
        or identity.user_id == "system"
        or target_owner in ["public", "system_public"]
        or (identity.is_authenticated and target_owner == identity.user_id)
        or (not identity.is_authenticated and target_owner in ["dev-user", "guest"])
    ):
        raise HTTPException(status_code=403, detail="Forbidden")

    pages = []
    extracted_path = EXTRACTED_DIR / f"{doc_id}.json"
    if extracted_path.exists():
        try:
            pages = json.loads(extracted_path.read_text(encoding="utf-8"))
        except Exception:
            pages = []

    if not pages:
        chunks = [c for c in vector_store.chunks if c.get("document_id") == doc_id or c.get("documentId") == doc_id]
        if chunks:
            pages = [{"page_number": c.get("page_number"), "section": c.get("section", ""), "text": c.get("content", "")} for c in chunks]

    orig_name = target.get("originalFilename") or target.get("original_filename") or doc_id
    mime = target.get("mimeType") or target.get("mime_type") or "text/plain"
    ext = Path(orig_name).suffix.lower().lstrip(".")
    fmt = "pdf" if ext == "pdf" else ("docx" if ext == "docx" else ("md" if ext in ["md", "markdown"] else "txt"))
    return {
        "id": doc_id,
        "document_id": doc_id,
        "originalFilename": orig_name,
        "mimeType": mime,
        "format": fmt,
        "sections": pages,
        "text": "\n\n".join(p.get("text", "") for p in pages)
    }

