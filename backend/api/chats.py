"""
Chats API Router for CogniFlow
Enforces strict per-user ownership and isolation for all conversation histories and messages.
Supports both persistent authenticated user accounts and isolated temporary guest sessions.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Response, status

from backend.models import (
    ConversationCreateRequest,
    MessageSaveRequest,
    ConversationSourceAttachRequest
)
from backend.services.db_service import (
    create_conversation,
    get_conversations_by_user,
    get_conversation,
    delete_conversation,
    save_message,
    update_conversation_title,
    attach_conversation_source,
    detach_conversation_source,
    list_conversation_source_documents,
    get_document
)
from backend.services.auth_service import get_optional_user
from backend.services.guest_session_service import guest_session_service

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("")
async def list_user_conversations(
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """Retrieve all conversations belonging to the authenticated user or guest session."""
    user_info = await get_optional_user(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if user_info.get("session_id"):
        response.headers["X-Session-ID"] = user_info["session_id"]

    if user_info["is_authenticated"]:
        convs = get_conversations_by_user(user_info["id"])
    else:
        convs = guest_session_service.get_conversations(user_info["id"])

    return {"ok": True, "conversations": convs}


@router.post("")
async def create_new_conversation(
    req: ConversationCreateRequest,
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """Create a new conversation assigned to the authenticated user or guest session."""
    user_info = await get_optional_user(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if user_info.get("session_id"):
        response.headers["X-Session-ID"] = user_info["session_id"]

    if user_info["is_authenticated"]:
        conv = create_conversation(
            user_id=user_info["id"],
            title=req.title,
            mode=req.mode or "deep_research",
            conv_id=req.id
        )
    else:
        import uuid
        conv_id = req.id or f"mission-{uuid.uuid4().hex[:12]}"
        conv = guest_session_service.save_conversation(
            session_id=user_info["id"],
            conv_id=conv_id,
            title=req.title,
            mode=req.mode or "deep_research"
        )

    return {"ok": True, "conversation": conv}


@router.get("/{conv_id}")
async def get_user_conversation(
    conv_id: str,
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """
    Retrieve full conversation and messages.
    Strictly verifies that conversation belongs to current user or guest session.
    Returns 404 if not found or if owned by another user.
    """
    user_info = await get_optional_user(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if user_info.get("session_id"):
        response.headers["X-Session-ID"] = user_info["session_id"]

    if user_info["is_authenticated"]:
        conv = get_conversation(conv_id=conv_id, user_id=user_info["id"])
    else:
        conv = guest_session_service.get_conversation(user_info["id"], conv_id)

    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access is not authorized."
        )
    return {"ok": True, "conversation": conv}


@router.delete("/{conv_id}")
async def delete_user_conversation(
    conv_id: str,
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """
    Delete conversation strictly owned by the authenticated user or guest session.
    Returns 404 if not found or unauthorized.
    """
    user_info = await get_optional_user(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if user_info.get("session_id"):
        response.headers["X-Session-ID"] = user_info["session_id"]

    if user_info["is_authenticated"]:
        success = delete_conversation(conv_id=conv_id, user_id=user_info["id"])
    else:
        success = guest_session_service.delete_conversation(user_info["id"], conv_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access is not authorized."
        )
    return {"ok": True, "message": "Conversation successfully deleted."}


@router.post("/{conv_id}/messages")
async def append_message(
    conv_id: str,
    req: MessageSaveRequest,
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """Append a message to an existing conversation owned by the authenticated user or guest session."""
    user_info = await get_optional_user(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if user_info.get("session_id"):
        response.headers["X-Session-ID"] = user_info["session_id"]

    if user_info["is_authenticated"]:
        conv = get_conversation(conv_id=conv_id, user_id=user_info["id"])
        if not conv:
            title = req.content[:45].strip() if req.role == "user" else "New Mission"
            conv = create_conversation(
                user_id=user_info["id"],
                title=title,
                conv_id=conv_id
            )

        msg = save_message(
            conv_id=conv_id,
            user_id=user_info["id"],
            role=req.role,
            content=req.content,
            metadata=req.metadata,
            msg_id=req.id
        )

        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Failed to save message to conversation."
            )

        if req.role == "user" and (conv.get("title") in ("New Mission", "Untitled Mission") or not conv.get("title")):
            new_title = req.content.strip()[:45]
            update_conversation_title(conv_id, user_info["id"], new_title)
    else:
        conv = guest_session_service.get_conversation(user_info["id"], conv_id)
        if not conv:
            title = req.content[:45].strip() if req.role == "user" else "New Mission"
            conv = guest_session_service.save_conversation(user_info["id"], conv_id, title)

        msg = guest_session_service.save_message(
            session_id=user_info["id"],
            conv_id=conv_id,
            role=req.role,
            content=req.content,
            metadata=req.metadata,
            msg_id=req.id
        )

    return {"ok": True, "message": msg}


@router.get("/{conv_id}/sources")
async def get_chat_sources(
    conv_id: str,
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """Retrieve all documents attached as sources to this conversation."""
    user_info = await get_optional_user(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if user_info.get("session_id"):
        response.headers["X-Session-ID"] = user_info["session_id"]

    if user_info["is_authenticated"]:
        conv = get_conversation(conv_id=conv_id, user_id=user_info["id"])
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        sources = list_conversation_source_documents(conv_id)
    else:
        conv = guest_session_service.get_conversation(user_info["id"], conv_id)
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        sources = guest_session_service.list_conversation_source_documents(user_info["id"], conv_id)

    return {"ok": True, "sources": sources}


@router.post("/{conv_id}/sources")
async def attach_chat_source(
    conv_id: str,
    req: ConversationSourceAttachRequest,
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """Attach a document from the user's library or guest session to this conversation."""
    user_info = await get_optional_user(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if user_info.get("session_id"):
        response.headers["X-Session-ID"] = user_info["session_id"]

    doc_id = req.document_id
    if user_info["is_authenticated"]:
        conv = get_conversation(conv_id=conv_id, user_id=user_info["id"])
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        doc = get_document(doc_id)
        if not doc or (doc.get("owner_id") != user_info["id"] and not user_info.get("is_admin")):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or unauthorized.")
        attach_conversation_source(conv_id, doc_id)
        sources = list_conversation_source_documents(conv_id)
    else:
        conv = guest_session_service.get_conversation(user_info["id"], conv_id)
        if not conv:
            conv = guest_session_service.save_conversation(user_info["id"], conv_id, "New Mission")
        doc = guest_session_service.get_document(user_info["id"], doc_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found or unauthorized.")
        guest_session_service.attach_conversation_source(user_info["id"], conv_id, doc_id)
        sources = guest_session_service.list_conversation_source_documents(user_info["id"], conv_id)

    return {"ok": True, "sources": sources}


@router.delete("/{conv_id}/sources/{doc_id}")
async def detach_chat_source(
    conv_id: str,
    doc_id: str,
    response: Response,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    """Detach a document from this conversation."""
    user_info = await get_optional_user(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    if user_info.get("session_id"):
        response.headers["X-Session-ID"] = user_info["session_id"]

    if user_info["is_authenticated"]:
        conv = get_conversation(conv_id=conv_id, user_id=user_info["id"])
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        detach_conversation_source(conv_id, doc_id)
        sources = list_conversation_source_documents(conv_id)
    else:
        conv = guest_session_service.get_conversation(user_info["id"], conv_id)
        if not conv:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
        guest_session_service.detach_conversation_source(user_info["id"], conv_id, doc_id)
        sources = guest_session_service.list_conversation_source_documents(user_info["id"], conv_id)

    return {"ok": True, "sources": sources}


