"""
Chat & Streaming SSE Router for CogniFlow
Executes adaptive multi-agent RAG pipeline with optional user session persistence.
"""

import json
from typing import Optional, AsyncGenerator
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import StreamingResponse

from backend.models import ChatQueryRequest
from backend.rag.pipeline import run_rag_pipeline
from backend.services.auth_service import get_optional_user
from backend.services.db_service import (
    get_conversation,
    create_conversation,
    save_message
)

router = APIRouter(tags=["chat"])


async def stream_with_persistence(
    gen: AsyncGenerator[str, None],
    user_id: str,
    conv_id: Optional[str],
    question: str,
    mode: str,
    is_authenticated: bool = False
) -> AsyncGenerator[str, None]:
    """
    Wraps the pipeline generator to persist user and assistant messages
    into Supabase (if authenticated) or GuestSessionService (if guest)
    after streaming finishes, without slowing down SSE delivery.
    """
    is_persisted = False
    if conv_id and user_id:
        try:
            if is_authenticated:
                conv = get_conversation(conv_id, user_id)
                if not conv:
                    create_conversation(user_id=user_id, title=question[:45].strip(), mode=mode, conv_id=conv_id)
                save_message(conv_id=conv_id, user_id=user_id, role="user", content=question)
            else:
                from backend.services.guest_session_service import guest_session_service
                guest_session_service.save_message(
                    session_id=user_id,
                    conv_id=conv_id,
                    role="user",
                    content=question
                )
            is_persisted = True
        except Exception:
            pass

    full_answer = ""
    pipeline_result = None

    async for chunk in gen:
        yield chunk
        if is_persisted:
            if chunk.startswith("data: "):
                try:
                    payload = json.loads(chunk[6:].strip())
                    if payload.get("type") == "pipeline_complete":
                        pipeline_result = payload.get("result", {})
                    elif payload.get("type") in ["token", "text_delta"]:
                        full_answer += payload.get("delta") or payload.get("content", "")
                except Exception:
                    pass

    if is_persisted and conv_id:
        try:
            answer_text = (pipeline_result.get("answer") if pipeline_result else full_answer) or ""
            metadata = {}
            if pipeline_result:
                metadata = {
                    "sources": pipeline_result.get("sources", []),
                    "citations": pipeline_result.get("citations", []),
                    "steps": pipeline_result.get("steps", []),
                    "plan": pipeline_result.get("plan"),
                    "confidence": pipeline_result.get("confidence"),
                    "answerability": pipeline_result.get("answerability"),
                    "documentCoverage": pipeline_result.get("documentCoverage"),
                    "totalDurationMs": pipeline_result.get("totalDurationMs", 0)
                }
            if answer_text:
                if is_authenticated:
                    save_message(
                        conv_id=conv_id,
                        user_id=user_id,
                        role="assistant",
                        content=answer_text,
                        metadata=metadata
                    )
                else:
                    from backend.services.guest_session_service import guest_session_service
                    guest_session_service.save_message(
                        session_id=user_id,
                        conv_id=conv_id,
                        role="assistant",
                        content=answer_text,
                        metadata=metadata
                    )
        except Exception:
            pass


@router.post("/api/chat")
async def chat_endpoint(
    req: ChatQueryRequest,
    request: Request,
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    x_session_id: Optional[str] = Header(None)
):
    question = req.get_question()
    if not question:
        raise HTTPException(status_code=400, detail="Missing question field")
    if len(question) > 1500:
        raise HTTPException(status_code=400, detail="Question exceeds 1500 characters")

    # Resolve authenticated user or fallback to server-issued guest session
    user_info = await get_optional_user(authorization=authorization, x_user_id=x_user_id, x_session_id=x_session_id)
    user_id = user_info["id"]
    is_authenticated = user_info.get("is_authenticated", False)
    session_id = user_info.get("session_id")

    mode = req.mode or "deep_research"
    conv_id = req.get_conversation_id()

    headers = {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Encoding": "none"
    }
    if session_id:
        headers["X-Session-ID"] = session_id

    pipeline_gen = run_rag_pipeline(
        question,
        user_id=user_id,
        mode=mode,
        request=request,
        document_id=req.document_id,
        sync_mode=bool(getattr(req, "sync", False))
    )

    wrapped_gen = stream_with_persistence(
        pipeline_gen,
        user_id=user_id,
        conv_id=conv_id,
        question=question,
        mode=mode,
        is_authenticated=is_authenticated
    )

    return StreamingResponse(
        wrapped_gen,
        media_type="text/event-stream",
        headers=headers
    )
