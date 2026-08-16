"""LLM provider interface."""

from __future__ import annotations

from typing import Protocol, Sequence

from ..models import ChatMessage


class LLMError(RuntimeError):
    """Application-level model failure safe to handle without exposing details."""


class LLMClient(Protocol):
    def chat(self, messages: Sequence[ChatMessage]) -> str:
        ...
