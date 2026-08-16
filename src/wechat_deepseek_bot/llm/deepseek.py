"""DeepSeek's OpenAI-compatible chat client."""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from ..models import ChatMessage
from .base import LLMError

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - exercised by the doctor, not unit tests
    OpenAI = None  # type: ignore[assignment]


class DeepSeekClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_tokens: int,
        timeout_seconds: float,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        if OpenAI is None:
            raise LLMError("The openai package is not installed")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.logger = logger or logging.getLogger(__name__)
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout_seconds)

    def chat(self, messages: Sequence[ChatMessage]) -> str:
        payload = [{"role": message.role, "content": message.content} for message in messages]
        self.logger.debug("DeepSeek request: %d messages", len(payload))
        try:
            response: Any = self._client.chat.completions.create(
                model=self.model,
                messages=payload,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        except Exception as exc:  # SDK exception types vary across versions.
            self.logger.exception("DeepSeek request failed (%s)", type(exc).__name__)
            raise LLMError("DeepSeek request failed") from exc

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as exc:
            self.logger.exception("DeepSeek returned an unexpected response")
            raise LLMError("DeepSeek returned an invalid response") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("DeepSeek returned an empty response")
        return content.strip()
