"""Trigger filtering and bot mention removal."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from ..models import IncomingMessage


@dataclass(frozen=True)
class RoutingDecision:
    accepted: bool
    prompt: str = ""
    reason: str = ""


def strip_bot_mention(content: str, bot_display_name: str = "") -> str:
    """Remove one leading or inline bot mention from a WeChat message."""

    text = content or ""
    if bot_display_name:
        mention = re.compile(r"@" + re.escape(bot_display_name) + r"(?:\u2005|\u00a0)?", re.IGNORECASE)
        text = mention.sub("", text, count=1)
    else:
        # wx4py normally reports is_at_me and may already strip the mention. This
        # fallback handles a raw "@Bot question" event without guessing a name.
        text = re.sub(r"^\s*@[^\s]+\s*", "", text, count=1)
    return text.strip()


class MessageRouter:
    def __init__(self, reply_only_when_at: bool = True, bot_display_name: str = "") -> None:
        self.reply_only_when_at = reply_only_when_at
        self.bot_display_name = bot_display_name

    def route(self, message: IncomingMessage, allow_without_mention: bool = False) -> RoutingDecision:
        if message.is_self:
            return RoutingDecision(False, reason="self message")
        if not (message.content or "").strip():
            return RoutingDecision(False, reason="empty message")
        if self.reply_only_when_at and not message.is_at_bot and not allow_without_mention:
            return RoutingDecision(False, reason="bot was not mentioned")

        prompt = strip_bot_mention(message.content, self.bot_display_name)
        if not prompt:
            return RoutingDecision(False, reason="empty prompt after mention removal")
        return RoutingDecision(True, prompt=prompt, reason="accepted")
