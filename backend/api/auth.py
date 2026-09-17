"""
Authentication API Router for CogniFlow
Endpoints for User Registration, Login, Logout, and Identity Verification.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, status

logger = logging.getLogger("cogniflow.auth")
from backend.models import (
    AuthRegisterRequest,
    AuthLoginRequest,
    AuthResponse,
    UserSafe
)
from backend.services.db_service import (
    create_user,
    get_user_by_email
)
from backend.services.auth_service import (
    validate_email_format,
    validate_password_strength,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
async def register(req: AuthRegisterRequest):
    name = (req.name or "").strip()
    email = (req.email or "").strip().lower()
    password = req.password or ""
    confirm_pwd = req.confirm_password

    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name is required."
        )

    if not validate_email_format(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please provide a valid email address."
        )

    is_valid_pwd, pwd_error = validate_password_strength(password)
    if not is_valid_pwd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=pwd_error
        )

    if confirm_pwd is not None and password != confirm_pwd:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match."
        )

    # Check duplicate email
    existing = get_user_by_email(email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists."
        )

    pwd_hash = hash_password(password)
    user = create_user(email=email, name=name, password_hash=pwd_hash)

    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "name": user["name"]
    })

    return AuthResponse(
        ok=True,
        token=token,
        user=UserSafe(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            createdAt=user["created_at"]
        )
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: AuthLoginRequest):
    email = (req.email or "").strip().lower()
    password = req.password or ""

    if not email or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email and password are required."
        )

    user = get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        # Generic error to prevent email enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please verify your credentials and try again."
        )

    token = create_access_token({
        "sub": user["id"],
        "email": user["email"],
        "name": user["name"]
    })

    return AuthResponse(
        ok=True,
        token=token,
        user=UserSafe(
            id=user["id"],
            email=user["email"],
            name=user["name"],
            createdAt=user["created_at"]
        )
    )


@router.post("/logout")
async def logout():
    return {"ok": True, "message": "Successfully logged out."}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    return {"ok": True, "user": current_user}


from typing import Optional
import json
from pydantic import BaseModel
from fastapi import Response, Header
from backend.services.guest_session_service import guest_session_service
from backend.services.db_service import db_service
from backend.services.storage_service import storage_service
from backend.rag.vector_store import vector_store


class MigrateGuestRequest(BaseModel):
    session_id: Optional[str] = None


@router.get("/guest-session")
async def get_or_create_guest_session(
    response: Response,
    x_session_id: Optional[str] = Header(None)
):
    """
    Returns an active, server-validated guest session token.
    If candidate token does not map to an active session, a new cryptographically
    random server session is issued.
    """
    clean_session = x_session_id.strip() if (x_session_id and x_session_id.strip()) else None
    session = guest_session_service.resolve_valid_session(clean_session)
    response.headers["X-Session-ID"] = session.session_id
    return {
        "ok": True,
        "sessionId": session.session_id,
        "isNew": session.session_id != clean_session
    }


@router.post("/migrate-guest-session")
async def migrate_guest_session(
    response: Response,
    body: Optional[MigrateGuestRequest] = None,
    x_session_id: Optional[str] = Header(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Idempotently transfers temporary guest conversation history and uploaded documents
    to the authenticated user account in Supabase and persistent storage.
    """
    candidate_id = (body.session_id if body and body.session_id else None) or x_session_id
    if candidate_id:
        candidate_id = candidate_id.strip()

    if not candidate_id or not guest_session_service.is_valid_session(candidate_id):
        return {
            "ok": True,
            "migrated": False,
            "detail": "No active guest session found to migrate."
        }

    session = guest_session_service.get_session(candidate_id)
    if not session or session.migrated:
        return {
            "ok": True,
            "migrated": False,
            "detail": "Guest session has already been migrated or is empty."
        }

    user_id = current_user["id"]
    convs_migrated = 0
    docs_migrated = 0

    # 1. Migrate conversations & messages to Supabase
    for conv_id, conv in list(session.conversations.items()):
        existing_conv = db_service.get_conversation(conv_id, user_id)
        if not existing_conv:
            db_service.create_conversation(
                user_id=user_id,
                title=conv.get("title", "Migrated Mission"),
                mode=conv.get("mode", "adaptive_rag"),
                conv_id=conv_id
            )
        for msg in conv.get("messages", []):
            db_service.save_message(
                conv_id=conv_id,
                user_id=user_id,
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                metadata=msg.get("metadata", {}),
                msg_id=msg.get("id")
            )
        convs_migrated += 1

    # 2. Migrate documents & chunks to Supabase, Storage, and Vector Store
    from backend.services.document_service import get_manifest, save_manifest
    manifest = get_manifest()
    docs_to_save_manifest = False

    for doc_id, doc in list(session.documents.items()):
        doc_entry = dict(doc)
        doc_entry["owner_id"] = user_id
        doc_entry["ownerId"] = user_id
        doc_entry["tenant_id"] = user_id
        doc_entry["tenantId"] = user_id
        doc_entry["r2_upload_key"] = doc_entry.get("r2_upload_key") or f"uploads/{doc_id}/original"
        doc_entry["r2_extracted_key"] = doc_entry.get("r2_extracted_key") or f"extracted/{doc_id}/pages.json"
        pages = doc.get("pages", [])
        chunks = doc.get("chunks", [])
        raw_bytes = doc.get("raw_bytes")

        # Save to DB
        existing_doc = db_service.get_document(doc_id)
        if not existing_doc:
            try:
                db_service.create_document(doc_entry)
            except Exception as e:
                logger.error(f"[Auth] Migration failed to save doc {doc_id} to DB: {e}")

        if chunks:
            for c in chunks:
                c["owner_id"] = user_id
                c["ownerId"] = user_id
                c["tenant_id"] = user_id
                c["tenantId"] = user_id
            try:
                db_service.save_chunks(doc_id, chunks)
            except Exception as e:
                logger.error(f"[Auth] Migration failed to save chunks for {doc_id} to DB: {e}")

        # Write to durable storage
        if raw_bytes:
            try:
                storage_service.put_object(f"uploads/{doc_id}/original", raw_bytes)
            except Exception as e:
                logger.error(f"[Auth] Migration failed to save raw bytes for {doc_id}: {e}")
        if pages:
            try:
                storage_service.put_object(f"extracted/{doc_id}/pages.json", json.dumps(pages).encode("utf-8"))
            except Exception as e:
                logger.error(f"[Auth] Migration failed to save extracted pages for {doc_id}: {e}")

        # Sync manifest
        clean_manifest_entry = dict(doc_entry)
        clean_manifest_entry.pop("raw_bytes", None)
        manifest = [m for m in manifest if (m.get("id") != doc_id and m.get("document_id") != doc_id)]
        manifest.append(clean_manifest_entry)
        docs_to_save_manifest = True

        docs_migrated += 1

    if docs_to_save_manifest:
        save_manifest(manifest)

    # 3. Update in-memory vector store ownership
    vector_store.migrate_owner(session.session_id, user_id)

    # 4. Mark session as migrated
    guest_session_service.mark_migrated(session.session_id)

    return {
        "ok": True,
        "migrated": True,
        "conversationsMigrated": convs_migrated,
        "documentsMigrated": docs_migrated
    }

