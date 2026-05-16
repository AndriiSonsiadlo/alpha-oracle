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


def get_groq_client() -> GroqLLMClient:
    return GroqLLMClient(get_settings().groq_api_key)


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
