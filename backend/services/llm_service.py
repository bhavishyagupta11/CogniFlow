"""
CogniFlow LLM Generation Service
Unified interface backed by ProviderManager (Gemini -> Secondary Remote -> Ollama -> Controlled Failure).
Strictly adheres to Pre-Execution Correction 1: No fake heuristic answers; genuine provider fallback telemetry.
"""

from typing import AsyncGenerator, Optional, List, Dict, Any
from backend.services.llm_provider import (
    provider_manager,
    sanitize_prompt_text,
    SECURITY_NOTICE
)


def sanitize_prompt_injection(text: str) -> str:
    """Sanitizes prompt injection vectors in retrieved text."""
    return sanitize_prompt_text(text)


async def stream_llm_response(
    user_prompt: str,
    system_prompt: str = "",
    sources: Optional[List[Dict[str, Any]]] = None,
    temperature: float = 0.3,
    max_tokens: int = 800,
    timeout_seconds: float = 25.0
) -> AsyncGenerator[str, None]:
    """
    Streams tokens from the configured LLM provider hierarchy:
    1. Primary Remote Provider (Gemini)
    2. Secondary Remote Provider (OpenRouter / OpenAI-compatible)
    3. Local Ollama Fallback
    4. Controlled Provider Failure (Honest failure message, zero hallucinated fallback).
    """
    async for event in provider_manager.stream_with_fallback(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds
    ):
        if event.get("type") == "token":
            yield event["delta"]


def get_latest_provider_telemetry() -> Dict[str, Any]:
    """Returns runtime telemetry from the most recent provider generation call."""
    return provider_manager.last_telemetry
