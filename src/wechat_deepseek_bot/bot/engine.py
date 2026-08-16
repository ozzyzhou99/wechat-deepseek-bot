"""Central application orchestration, independent of wx4py."""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import defaultdict
from threading import Lock
from typing import Optional

from ..memory.conversation import ConversationStore
from ..models import ChatMessage, IncomingMessage
from ..prompts import DEFAULT_SYSTEM_PROMPT
from ..llm.base import LLMClient, LLMError
from ..content_filter import PoliticsFilter
from .commands import CommandHandler
from .router import MessageRouter
from ..utils.ingress_logging import message_context, redact_identifier


TEMPORARY_ERROR_TEXT = "AI 服务暂时不可用，请稍后再试。"


class BotEngine:
    def __init__(
        self,
        router: MessageRouter,
        store: ConversationStore,
        command_handler: CommandHandler,
        llm: LLMClient,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        logger: Optional[logging.Logger] = None,
        archive=None,
        sessions=None,
        persona_manager=None,
        games=None,
        ambient_reply_enabled: bool = False,
        politics_filter: Optional[PoliticsFilter] = None,
    ) -> None:
        self.router = router
        self.store = store
        self.command_handler = command_handler
        self.llm = llm
        self.system_prompt = system_prompt
        self.logger = logger or logging.getLogger(__name__)
        self._group_locks = defaultdict(Lock)
        self.archive = archive
        self.sessions = sessions
        self.persona_manager = persona_manager
        self.games = games
        self.ambient_reply_enabled = ambient_reply_enabled
        self.politics_filter = politics_filter

    @staticmethod
    def _sender_key(message: IncomingMessage) -> Optional[str]:
        """Return a stable sender key, or None when the transport has no identity.

        wx4py 0.2.x currently does not expose the sender on MessageEvent. Treating
        that missing value as the literal key ``unknown`` would share one active
        session with every member of the group.
        """

        if message.sender_id and message.sender_id.strip():
            return f"id:{message.sender_id.strip()}"
        if message.sender_name:
            normalized = unicodedata.normalize("NFKC", message.sender_name)
            normalized = re.sub(r"\s+", " ", normalized).strip().casefold()
            if normalized not in {"", "unknown", "none"}:
                return f"name:{normalized}"
        return None

    def _ambient_candidate(self, message: IncomingMessage) -> bool:
        if not self.ambient_reply_enabled or message.is_at_bot or not message.content.strip():
            return False
        content = message.content.lower()
        return any(cue in content for cue in ("机器人呢", "hh呢", "@hh", "笑死", "救命", "绷不住"))

    @staticmethod
    def _is_group_message(message: IncomingMessage) -> bool:
        """Hook private messages use a synthetic ``private:`` group key."""

        return bool(message.group_id) and not message.group_id.casefold().startswith("private:") and message.group_id != "private"

    def _record_successful_reply(
        self,
        message: IncomingMessage,
        sender_key: Optional[str],
        *,
        explicit_invocation: bool,
        followup_allowed: bool,
        safe_group: str,
    ) -> None:
        if self.sessions is None or sender_key is None:
            return
        if explicit_invocation:
            self.sessions.activate(message.group_id, sender_key)
            self.logger.debug(
                "group_followup_session_created group=%s sender=%s",
                safe_group,
                redact_identifier(sender_key),
            )
        elif followup_allowed:
            session = self.sessions.record_followup(message.group_id, sender_key)
            if session is None:
                self.logger.debug(
                    "group_followup_expired group=%s sender=%s",
                    safe_group,
                    redact_identifier(sender_key),
                )
            elif session.active:
                self.logger.debug(
                    "group_followup_allowed group=%s sender=%s count=%s",
                    safe_group,
                    redact_identifier(sender_key),
                    session.followup_count,
                )
            else:
                self.logger.debug(
                    "group_followup_limit_reached group=%s sender=%s",
                    safe_group,
                    redact_identifier(sender_key),
                )

    def discard_followup_session(self, message: IncomingMessage) -> None:
        """Clear continuation permission when the transport cannot deliver a reply."""

        if self.sessions is None:
            return
        sender_key = self._sender_key(message)
        if sender_key is not None:
            self.sessions.clear(message.group_id, sender_key)

    def handle(self, message: IncomingMessage) -> Optional[str]:
        is_hook = message.raw_payload is not None
        transport = "hook" if is_hook else "wechat"

        def safe_group() -> str:
            return redact_identifier(message.group_id) if is_hook else message.group_name

        if self.archive is not None:
            try:
                self.archive.archive_message(message)
            except Exception:
                self.logger.exception("failed to archive message group=%s", safe_group())

        sender_key = self._sender_key(message)
        if (
            self.sessions is not None
            and sender_key
            and not message.is_self
            and message.content.strip()
            and self._is_group_message(message)
        ):
            invalidated = self.sessions.break_other_users(message.group_id, sender_key)
            if invalidated:
                self.logger.debug(
                    "group_followup_broken_by_other_sender group=%s sender=%s invalidated=%s",
                    safe_group(),
                    redact_identifier(sender_key),
                    invalidated,
                )
        followup_allowed = bool(
            self.router.reply_only_when_at
            and self.sessions
            and sender_key
            and self.sessions.can_followup(message.group_id, sender_key)
        )
        active_session = followup_allowed
        active_game = bool(self.games and self.games.is_active(message.group_id))
        ambient_candidate = self._ambient_candidate(message)
        allow_without_mention = followup_allowed or active_game or ambient_candidate
        if is_hook:
            activation_ok = (
                not self.router.reply_only_when_at
                or message.is_at_bot
                or active_session
                or active_game
                or ambient_candidate
            )
            activation_reason = (
                "at_bot" if message.is_at_bot else
                "active_session" if active_session else
                "active_game" if active_game else
                "ambient" if ambient_candidate else
                "not_activated"
            )
            self.logger.info(
                "HOOK ACTIVATION %s reason=%s %s",
                "accepted" if activation_ok else "rejected",
                activation_reason,
                message_context(message, transport),
            )
        decision = self.router.route(message, allow_without_mention=allow_without_mention)
        if is_hook:
            self.logger.info(
                "HOOK ROUTER %s reason=%s %s",
                "accepted" if decision.accepted else "rejected",
                decision.reason.replace(" ", "_"),
                message_context(message, transport),
            )
            if not decision.accepted:
                ignored_reason = {
                    "bot was not mentioned": "not_activated",
                    "self message": "self",
                    "empty message": "empty",
                    "empty prompt after mention removal": "empty_prompt",
                }.get(decision.reason, decision.reason.replace(" ", "_"))
                self.logger.info(
                    "HOOK INBOUND ignored reason=%s %s",
                    ignored_reason,
                    message_context(message, transport),
                )
        else:
            self.logger.info(
                "message group=%s sender=%s at_bot=%s self=%s accepted=%s reason=%s",
                message.group_name,
                message.sender_name or "unknown",
                message.is_at_bot,
                message.is_self,
                decision.accepted,
                decision.reason,
            )
        if not decision.accepted:
            if not message.is_at_bot and not followup_allowed and not active_game and not ambient_candidate:
                self.logger.debug(
                    "group_message_ignored_no_invocation group=%s sender=%s",
                    safe_group(),
                    redact_identifier(sender_key or message.sender_name or "unknown"),
                )
            return None

        if self.politics_filter is not None:
            filter_result = self.politics_filter.check(decision.prompt)
            if filter_result.blocked:
                self.logger.info(
                    "message blocked by politics filter group=%s reason=%s",
                    safe_group(),
                    filter_result.reason,
                )
                return self.politics_filter.reply

        # wx4py uses asynchronous callbacks. The lock serializes complete model
        # turns for one group while allowing different groups to proceed together.
        with self._group_locks[message.group_id]:
            handle_message = getattr(self.command_handler, "handle_message", None)
            if handle_message is not None:
                command = handle_message(decision.prompt, message, self.llm)
            else:
                command = self.command_handler.handle(decision.prompt, message.group_id)
            if command is not None:
                self._record_successful_reply(
                    message,
                    sender_key,
                    explicit_invocation=message.is_at_bot,
                    followup_allowed=followup_allowed,
                    safe_group=safe_group(),
                )
                return command.response

            history = self.store.get_history(message.group_id)
            system_prompt = self.system_prompt
            if self.persona_manager is not None:
                system_prompt = self.persona_manager.system_prompt(
                    message.group_id,
                    decision.prompt,
                    self.system_prompt,
                    turn_index=self.store.turn_count(message.group_id),
                )
            messages = [ChatMessage("system", system_prompt)]
            messages.extend(history)
            messages.append(ChatMessage("user", decision.prompt))
            self.logger.info("DeepSeek request start group=%s", safe_group())
            try:
                response = self.llm.chat(messages)
            except LLMError:
                self.logger.exception("DeepSeek request failed group=%s", safe_group())
                return TEMPORARY_ERROR_TEXT
            except Exception:
                self.logger.exception("Unexpected model error group=%s", safe_group())
                return TEMPORARY_ERROR_TEXT

            self.store.append_user(message.group_id, decision.prompt)
            self.store.append_assistant(message.group_id, response)
            self._record_successful_reply(
                message,
                sender_key,
                explicit_invocation=message.is_at_bot,
                followup_allowed=followup_allowed,
                safe_group=safe_group(),
            )
            self.logger.info("DeepSeek request end group=%s", safe_group())
            return response
