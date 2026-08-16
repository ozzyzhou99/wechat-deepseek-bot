"""Redacted fields used by transport ingress diagnostics."""

from __future__ import annotations

import hashlib
from typing import Any

from ..models import IncomingMessage


def redact_identifier(value: Any) -> str:
    """Return a stable, non-reversible log token for an identifier."""

    text = "" if value is None else str(value).strip()
    if not text:
        return "<none>"
    return f"redacted:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}"


def message_context(message: IncomingMessage, transport: str = "hook") -> str:
    """Return only safe, normalized message fields for an ingress log line."""

    return (
        f"message_id={redact_identifier(message.message_id)} "
        f"group_id={redact_identifier(message.group_id)} "
        f"sender_id={redact_identifier(message.sender_id)} "
        f"is_at_bot={message.is_at_bot} is_self={message.is_self} transport={transport}"
    )
