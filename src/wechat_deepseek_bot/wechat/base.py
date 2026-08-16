"""Transport contracts for an official or explicitly authorized adapter."""

from __future__ import annotations

from typing import Any, Optional, Protocol, Sequence


class WeChatTransport(Protocol):
    """Small lifecycle contract used by the application bootstrap."""

    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def run(self) -> None:
        ...

    def send_text(self, chat_id: str, text: str) -> None:
        ...

    def send_at(self, chat_id: str, user_id: str, text: str) -> None:
        ...

    def is_logged_in(self) -> bool:
        ...

    def get_self_id(self) -> Optional[str]:
        ...

    def get_self_identity(self) -> Any:
        ...

    def get_group_members(self, group_id: str) -> Sequence[Any]:
        ...
