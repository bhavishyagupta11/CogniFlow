"""
Chats API Router for CogniFlow
Enforces strict per-user ownership and isolation for all conversation histories and messages.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status

from backend.models import (
    ConversationCreateRequest,
    MessageSaveRequest
)
from backend.services.db_service import (
    create_conversation,
    get_conversations_by_user,
    get_conversation,
    delete_conversation,
    save_message,
    update_conversation_title
)
from backend.services.auth_service import get_current_user

router = APIRouter(prefix="/api/chats", tags=["chats"])


@router.get("")
async def list_user_conversations(current_user: dict = Depends(get_current_user)):
    """Retrieve all conversations belonging to the authenticated user."""
    convs = get_conversations_by_user(current_user["id"])
    return {"ok": True, "conversations": convs}


@router.post("")
async def create_new_conversation(
    req: ConversationCreateRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new conversation assigned to the authenticated user."""
    conv = create_conversation(
        user_id=current_user["id"],
        title=req.title,
        mode=req.mode or "deep_research",
        conv_id=req.id
    )
    return {"ok": True, "conversation": conv}


@router.get("/{conv_id}")
async def get_user_conversation(
    conv_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve full conversation and messages.
    Strictly verifies that conversation belongs to current_user.
    Returns 404 if not found or if owned by another user.
    """
    conv = get_conversation(conv_id=conv_id, user_id=current_user["id"])
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access is not authorized."
        )
    return {"ok": True, "conversation": conv}


@router.delete("/{conv_id}")
async def delete_user_conversation(
    conv_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete conversation strictly owned by the authenticated user.
    Returns 404 if not found or unauthorized.
    """
    success = delete_conversation(conv_id=conv_id, user_id=current_user["id"])
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
    current_user: dict = Depends(get_current_user)
):
    """Append a message to an existing conversation owned by the authenticated user."""
    # Ensure conversation exists and is owned by user
    conv = get_conversation(conv_id=conv_id, user_id=current_user["id"])
    if not conv:
        # If conversation doesn't exist yet, auto-create it with title from message if user message
        title = req.content[:45].strip() if req.role == "user" else "New Mission"
        conv = create_conversation(
            user_id=current_user["id"],
            title=title,
            conv_id=conv_id
        )

    msg = save_message(
        conv_id=conv_id,
        user_id=current_user["id"],
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

    # If title was default, update it from first user message
    if req.role == "user" and (conv.get("title") in ("New Mission", "Untitled Mission") or not conv.get("title")):
        new_title = req.content.strip()[:45]
        update_conversation_title(conv_id, current_user["id"], new_title)

    return {"ok": True, "message": msg}
