"""Modular LLM client supporting OpenAI and Gemini providers.

Swap providers by changing LLM_PROVIDER in .env — the rest of the codebase
remains untouched thanks to the unified interface.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import httpx

from business_twin_ai.config import settings

logger = logging.getLogger(__name__)


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract the first JSON object from LLM text output."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code blocks
    patterns = [
        r"```json\s*\n?(.*?)\n?\s*```",
        r"```\s*\n?(.*?)\n?\s*```",
        r"(\{.*\})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not extract JSON from LLM response: {text[:200]}...")


class BaseLLMClient(ABC):
    """Abstract base for LLM clients."""

    @abstractmethod
    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Send a chat completion request and return the raw text response."""
        ...

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send a chat request and parse the JSON response."""
        response = await self.chat(system_prompt, user_prompt, temperature, max_tokens)
        return _extract_json(response)


class OpenAIClient(BaseLLMClient):
    """OpenAI API client using httpx (no SDK dependency)."""

    BASE_URL = "https://api.openai.com/v1"

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        temperature = temperature or settings.LLM_TEMPERATURE
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(f"{self.BASE_URL}/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


class GeminiClient(BaseLLMClient):
    """Google Gemini API client using httpx."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        temperature = temperature or settings.LLM_TEMPERATURE
        max_tokens = max_tokens or settings.LLM_MAX_TOKENS

        model = settings.LLM_MODEL or "gemini-pro"
        url = f"{self.BASE_URL}/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"

        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]


class FallbackClient(BaseLLMClient):
    """Fallback client that raises to trigger rule-based fallbacks when no LLM is configured.
    
    Useful for development, testing, and demos without an API key.
    Each engine has rule-based fallback handlers that activate when this client is used.
    """

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        logger.info("Using FallbackClient — triggering rule-based fallbacks.")
        raise NotImplementedError(
            "No LLM API key configured. Using rule-based fallback."
        )


def get_llm_client() -> BaseLLMClient:
    """Factory: return the appropriate LLM client based on configuration."""
    provider = settings.LLM_PROVIDER.lower()

    if provider == "openai" and settings.OPENAI_API_KEY:
        return OpenAIClient()
    elif provider == "gemini" and settings.GEMINI_API_KEY:
        return GeminiClient()
    else:
        logger.info("No LLM API key configured — using FallbackClient")
        return FallbackClient()
