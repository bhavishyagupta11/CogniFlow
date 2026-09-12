"""
Chat & Streaming SSE Router
"""

from typing import Optional
from fastapi import APIRouter, Request, Header, HTTPException
from fastapi.responses import StreamingResponse

from backend.models import ChatQueryRequest
from backend.rag.pipeline import run_rag_pipeline

router = APIRouter(tags=["chat"])


@router.post("/api/chat")
async def chat_endpoint(
    req: ChatQueryRequest,
    request: Request,
    x_user_id: Optional[str] = Header(None)
):
    question = req.get_question()
    if not question:
        raise HTTPException(status_code=400, detail="Missing question field")
    if len(question) > 1500:
        raise HTTPException(status_code=400, detail="Question exceeds 1500 characters")

    user_id = x_user_id or "dev-user"
    mode = req.mode or "deep_research"

    headers = {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        "Content-Encoding": "none"
    }

    return StreamingResponse(
        run_rag_pipeline(question, user_id=user_id, mode=mode, request=request),
        media_type="text/event-stream",
        headers=headers
    )
