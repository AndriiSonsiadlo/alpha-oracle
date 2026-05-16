"""Pluggable LLM provider clients behind one common interface."""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Common async interface for chat-completion providers."""

    provider: str = "base"

    @abstractmethod
    async def _complete_text(
        self, system: str, user: str, model: str, *, temperature: float, max_tokens: int
    ) -> str:
        """Return the raw text completion from the provider."""

    async def complete_json(
        self,
        system: str,
        user: str,
        model: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> dict:
        raw = await self._complete_text(
            system, user, model, temperature=temperature, max_tokens=max_tokens
        )
        return _extract_json(raw)


def _extract_json(text: str) -> dict:
    if not text:
        return {}
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}


class GroqLLMClient(LLMClient):
    provider = "groq"

    def __init__(self, api_key: str):
        from groq import AsyncGroq
        self._client = AsyncGroq(api_key=api_key)

    async def _complete_text(self, system, user, model, *, temperature, max_tokens):
        resp = await self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_completion_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or "{}"


class OpenAILLMClient(LLMClient):
    provider = "openai"

    def __init__(self, api_key: str):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key)

    async def _complete_text(self, system, user, model, *, temperature, max_tokens):
        resp = await self._client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return resp.choices[0].message.content or "{}"


class AnthropicLLMClient(LLMClient):
    provider = "anthropic"

    def __init__(self, api_key: str):
        from anthropic import AsyncAnthropic
        self._client = AsyncAnthropic(api_key=api_key)

    async def _complete_text(self, system, user, model, *, temperature, max_tokens):
        # Claude has no JSON response_format. Prefill "{" to force JSON output.
        resp = await self._client.messages.create(
            model=model,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "user", "content": user},
                {"role": "assistant", "content": "{"},
            ],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        return "{" + text


class GoogleLLMClient(LLMClient):
    provider = "google"

    def __init__(self, api_key: str):
        from google import genai
        self._client = genai.Client(api_key=api_key)

    async def _complete_text(self, system, user, model, *, temperature, max_tokens):
        from google.genai import types
        resp = await self._client.aio.models.generate_content(
            model=model,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            ),
        )
        return resp.text or "{}"


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

from functools import lru_cache

MODEL_PROVIDERS: dict[str, str] = {
    "llama-3.3-70b-versatile": "groq",
    "llama-3.1-8b-instant": "groq",
    "openai/gpt-oss-20b": "groq",
    "gemini-2.0-flash": "google",
    "gemini-1.5-flash": "google",
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "gpt-4-turbo": "openai",
    "gpt-5-mini": "openai",
    "gpt-5.4-nano": "openai",
    "claude-opus-4-8": "anthropic",
    "claude-sonnet-4-6": "anthropic",
    "claude-haiku-4-5": "anthropic",
}

_CLIENT_FACTORIES = {
    "groq": lambda s: GroqLLMClient(s.groq_api_key),
    "openai": lambda s: OpenAILLMClient(s.openai_api_key),
    "anthropic": lambda s: AnthropicLLMClient(s.anthropic_api_key),
    "google": lambda s: GoogleLLMClient(s.google_api_key),
}


def resolve_provider(model: str, override: Optional[str] = None) -> str:
    if override and override.lower() != "auto":
        return override.lower()
    if model in MODEL_PROVIDERS:
        return MODEL_PROVIDERS[model]
    m = (model or "").lower()
    if "gpt-oss" in m:
        return "groq"
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gemini"):
        return "google"
    if m.startswith(("gpt", "o1", "o3", "o4", "chatgpt")):
        return "openai"
    return "groq"


@lru_cache(maxsize=None)
def get_llm_client(provider: str) -> LLMClient:
    factory = _CLIENT_FACTORIES.get(provider)
    if not factory:
        raise ValueError(f"Unknown LLM provider: {provider!r}")
    return factory(get_settings())


def get_client_for_model(model: str, override: Optional[str] = None) -> LLMClient:
    return get_llm_client(resolve_provider(model, override))
