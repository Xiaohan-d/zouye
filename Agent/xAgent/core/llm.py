from __future__ import annotations

from openai import AsyncOpenAI

from .config import LLMSettings


def create_async_client(settings: LLMSettings) -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=settings.base_url,
        api_key=settings.api_key or "not-needed",
    )
