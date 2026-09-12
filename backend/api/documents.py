"""
Document Management Router
Handles listing, file ingestion (PyMuPDF), document deletion, and PDF serving.
"""

from typing import List, Optional, Union
from pathlib import Path
from fastapi import APIRouter, Header, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse

from backend.config import UPLOADS_DIR, UPLOAD_ACCESS_KEY
from backend.services.document_service import get_manifest, ingest_file, delete_document, reindex_document, inspect_document

router = APIRouter(tags=["documents"])


@router.get("/api/documents")
async def list_documents(x_user_id: Optional[str] = Header(None)):
    user_id = x_user_id or "dev-user"
    manifest = get_manifest()
    
    # Return user-owned, public, or unassigned documents
    filtered = []
    allowed_owners = [user_id, "system_public", "public"]
    if user_id in ["dev-user", "user_default"]:
        allowed_owners.extend(["dev-user", "user_default"])

    for m in manifest:
        owner = m.get("ownerId") or m.get("owner_id")
        if not owner or owner in allowed_owners:
            # Ensure both ownerId and owner_id are present for contract parity
            doc = dict(m)
            doc["ownerId"] = owner or user_id
            doc["owner_id"] = owner or user_id
            doc["indexStatus"] = m.get("indexStatus", "indexed")
            filtered.append(doc)
            
    return filtered


@router.post("/api/documents")
async def upload_documents(
    file: Union[UploadFile, List[UploadFile]] = File(...),
    x_user_id: Optional[str] = Header(None),
    x_access_key: Optional[str] = Header(None)
):
    # Access key validation: if configured and provided key does not match
    if UPLOAD_ACCESS_KEY and x_access_key:
        if x_access_key.strip() != UPLOAD_ACCESS_KEY.strip():
            return JSONResponse(
                status_code=401,
                content={
                    "ok": False,
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "Invalid access key. Please verify your credentials in Settings."
                    }
                }
            )

    user_id = x_user_id or "dev-user"
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

    results = []
    for f in file_list:
        try:
            content = await f.read()
            res = await ingest_file(
                file_bytes=content,
                filename=f.filename or "uploaded_file.pdf",
                mime_type=f.content_type or "application/pdf",
                owner_id=user_id
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
    if len(results) == 1:
        first = results[0]
        status_code = first.get("status", 200)
        
        if not first.get("ok"):
            return JSONResponse(
                status_code=status_code,
                content={
                    "ok": False,
                    "error": first.get("error", {"code": "UPLOAD_FAILED", "message": "Upload failed."}),
                    "results": results
                }
            )

        doc = first.get("document", {})
        return JSONResponse(
            status_code=200,
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
    x_user_id: Optional[str] = Header(None)
):
    user_id = x_user_id or "dev-user"
    success = delete_document(doc_id, owner_id=user_id)
    if not success:
        return JSONResponse(
            status_code=404,
            content={
                "ok": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": f"Document '{doc_id}' not found or unauthorized for deletion."
                }
            }
        )
    return {"ok": True, "id": doc_id, "message": "Document deleted successfully"}


@router.get("/api/documents/{doc_id}/pdf")
@router.get("/api/documents/{doc_id}/raw")
async def view_document_pdf(doc_id: str):
    manifest = get_manifest()
    target = next((m for m in manifest if m.get("id") == doc_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Document not found in manifest")

    filename = target.get("filename")
    if not filename:
        raise HTTPException(status_code=404, detail="Document record contains no file reference")

    safe_filename = Path(filename).name
    pdf_path = (UPLOADS_DIR / safe_filename).resolve()

    if not pdf_path.is_relative_to(UPLOADS_DIR.resolve()) or not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Binary file not found on disk")

    media_type = target.get("mimeType", "application/pdf")
    if not media_type or media_type == "application/octet-stream":
        media_type = "application/pdf" if safe_filename.endswith(".pdf") else "text/plain"

    original_name = target.get("originalFilename", safe_filename)
    return FileResponse(
        path=str(pdf_path),
        media_type=media_type,
        filename=original_name,
        headers={
            "Content-Disposition": f'inline; filename="{original_name}"',
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=3600"
        }
    )


@router.post("/api/documents/{doc_id}/reindex")
async def reindex_single_document(
    doc_id: str,
    x_user_id: Optional[str] = Header(None)
):
    user_id = x_user_id or "dev-user"
    res = reindex_document(doc_id, owner_id=user_id)
    status_code = res.get("status", 200)
    return JSONResponse(status_code=status_code, content=res)


@router.get("/api/documents/{doc_id}/inspect")
async def inspect_single_document(doc_id: str):
    res = inspect_document(doc_id)
    status_code = 200 if res.get("valid") else 404
    return JSONResponse(status_code=status_code, content=res)

