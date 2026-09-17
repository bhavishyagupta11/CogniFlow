"""
Document Management Router
Handles listing, file ingestion (PyMuPDF), document deletion, and PDF serving.
"""

from typing import List, Optional, Union
from pathlib import Path
from typing import List, Optional, Union
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException, UploadFile, File, Form, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from backend.config import UPLOADS_DIR
from backend.services.document_service import get_manifest, ingest_file, delete_document, reindex_document, inspect_document
from backend.services.auth_service import resolve_caller_identity, get_optional_user

router = APIRouter(tags=["documents"])


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


@router.post("/api/documents")
async def upload_documents(
    response: Response,
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
            res = await ingest_file(
                file_bytes=content,
                filename=f.filename or "uploaded_file.pdf",
                mime_type=f.content_type or "application/pdf",
                owner_id=identity.user_id,
                is_authenticated=identity.is_authenticated,
                password=doc_password
            )
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
        return JSONResponse(
            status_code=200,
            headers={"X-Session-ID": identity.session_id} if identity.session_id else None,
            content={
                "ok": True,
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


@router.get("/api/documents/{doc_id}/pdf")
@router.get("/api/documents/{doc_id}/raw")
async def view_document_pdf(
    doc_id: str,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None)
):
    from backend.services.db_service import db_service
    from backend.services.storage_service import storage_service, R2StorageService

    # 1. Authorization check first (Phase 6)
    identity = await resolve_caller_identity(authorization=authorization, x_user_id=x_user_id)
    target = db_service.get_document(doc_id)
    if not target:
        manifest = get_manifest()
        target = next((m for m in manifest if m.get("id") == doc_id or m.get("document_id") == doc_id), None)
        if not target:
            raise HTTPException(status_code=404, detail="Document not found")

    target_owner = target.get("ownerId") or target.get("owner_id")
    target_workspace = target.get("workspace") or target.get("workspace_id") or target.get("workspaceId")

    # Authorization policy
    if identity.is_admin or identity.user_id == "system":
        allowed = True
    elif target_owner in ["public", "system_public"]:
        allowed = True
    elif identity.is_authenticated:
        allowed = (target_owner == identity.user_id)
    else:
        # Guest workspace
        allowed = (target_owner in ["dev-user", "guest", "user_default"] or target_workspace in ["guest", "dev"])

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Caller '{identity.user_id}' is not authorized to access document '{doc_id}'"
        )

    safe_filename = target.get("originalFilename") or target.get("original_filename") or f"{doc_id}.pdf"
    media_type = target.get("mimeType") or target.get("mime_type") or "application/pdf"
    if not media_type or media_type == "application/octet-stream":
        media_type = "application/pdf" if safe_filename.endswith(".pdf") else "text/plain"

    r2_upload_key = target.get("r2_upload_key") or f"uploads/{doc_id}/original"
    filename = target.get("filename") or f"{doc_id}.pdf"

    # 2. Cloudflare R2 short-lived signed URL
    if isinstance(storage_service, R2StorageService):
        try:
            presigned_url = storage_service.generate_presigned_url(r2_upload_key, expires_in_seconds=300)
            return RedirectResponse(url=presigned_url, status_code=307)
        except Exception as e:
            pass

    # 3. Object storage stream
    try:
        if storage_service.exists(r2_upload_key):
            content = storage_service.get_object(r2_upload_key)
            return Response(
                content=content,
                media_type=media_type,
                headers={
                    "Content-Disposition": f'inline; filename="{safe_filename}"',
                    "Accept-Ranges": "bytes",
                    "Cache-Control": "private, max-age=300"
                }
            )
    except Exception:
        pass

    # 4. Local filesystem fallback
    safe_disk_name = Path(filename).name
    pdf_path = (UPLOADS_DIR / safe_disk_name).resolve()
    if pdf_path.is_relative_to(UPLOADS_DIR.resolve()) and pdf_path.exists():
        return FileResponse(
            path=str(pdf_path),
            media_type=media_type,
            filename=safe_filename,
            headers={
                "Content-Disposition": f'inline; filename="{safe_filename}"',
                "Accept-Ranges": "bytes",
                "Cache-Control": "private, max-age=300"
            }
        )

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


@router.get("/api/documents/{doc_id}/inspect")
async def inspect_single_document(doc_id: str):
    res = inspect_document(doc_id)
    status_code = 200 if res.get("valid") else 404
    return JSONResponse(status_code=status_code, content=res)

