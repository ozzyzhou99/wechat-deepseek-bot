"""Bounded, in-memory conversation history separated by group."""

from __future__ import annotations

from collections import deque
from threading import RLock
from typing import Deque, Dict, List

from ..models import ChatMessage


class ConversationStore:
    """Store complete user/assistant turns independently for each group."""

    def __init__(self, max_turns: int = 10) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be at least 1")
        self.max_turns = max_turns
        self._histories: Dict[str, Deque[ChatMessage]] = {}
        self._lock = RLock()

    def _history(self, group_id: str) -> Deque[ChatMessage]:
        history = self._histories.get(group_id)
        if history is None:
            history = deque(maxlen=self.max_turns * 2)
            self._histories[group_id] = history
        return history

    def get_history(self, group_id: str) -> List[ChatMessage]:
        with self._lock:
            return list(self._history(group_id))

    def append_user(self, group_id: str, content: str) -> None:
        with self._lock:
            self._history(group_id).append(ChatMessage("user", content))

    def append_assistant(self, group_id: str, content: str) -> None:
        with self._lock:
            self._history(group_id).append(ChatMessage("assistant", content))

    def clear(self, group_id: str) -> None:
        with self._lock:
            self._histories.pop(group_id, None)

    def turn_count(self, group_id: str) -> int:
        with self._lock:
            return len(self._history(group_id)) // 2
