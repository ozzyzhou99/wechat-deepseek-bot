"""Internal data models shared by the application layers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Optional


Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class IncomingMessage:
    group_id: str
    group_name: str
    sender_id: Optional[str]
    sender_name: str
    content: str
    is_at_bot: bool
    is_self: bool
    timestamp: Optional[datetime] = None
    message_id: Optional[str] = None
    platform_message_type: Optional[str] = None
    platform: str = "wechat"
    raw_message_type: Optional[str] = None
    raw_content: Optional[str] = None
    raw_payload: Optional[Any] = None


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str
