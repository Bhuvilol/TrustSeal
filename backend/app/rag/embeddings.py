from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ..core.config import settings


def _resolve_provider_credentials() -> tuple[str, str, Dict[str, str]]:
    api_key = settings.OPENAI_API_KEY or settings.OPENROUTER_API_KEY
    if not api_key:
        raise ValueError(
            "No LLM API key configured. Set OPENAI_API_KEY or OPENROUTER_API_KEY."
        )

    if settings.OPENAI_API_KEY:
        base_url = settings.OPENAI_BASE_URL or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    else:
        base_url = settings.OPENROUTER_BASE_URL

    headers: Dict[str, str] = {}
    if settings.OPENROUTER_SITE_URL:
        headers["HTTP-Referer"] = settings.OPENROUTER_SITE_URL
    if settings.OPENROUTER_APP_NAME:
        headers["X-Title"] = settings.OPENROUTER_APP_NAME

    return api_key, base_url, headers


@lru_cache(maxsize=1)
def get_embeddings_client() -> OpenAIEmbeddings:
    api_key, base_url, headers = _resolve_provider_credentials()
    return OpenAIEmbeddings(
        model=settings.AGENTIC_EMBEDDING_MODEL,
        dimensions=settings.RAG_EMBEDDING_DIMENSION,
        openai_api_key=api_key,
        openai_api_base=base_url,
        request_timeout=settings.OPENROUTER_TIMEOUT_SECONDS,
        default_headers=headers or None,
    )


@lru_cache(maxsize=8)
def get_chat_model(temperature: float, max_tokens: int) -> ChatOpenAI:
    api_key, base_url, headers = _resolve_provider_credentials()
    return ChatOpenAI(
        model_name=settings.AGENTIC_LLM_MODEL,
        openai_api_key=api_key,
        openai_api_base=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        request_timeout=settings.OPENROUTER_TIMEOUT_SECONDS,
        default_headers=headers or None,
    )


def clear_model_caches() -> None:
    get_embeddings_client.cache_clear()
    get_chat_model.cache_clear()
