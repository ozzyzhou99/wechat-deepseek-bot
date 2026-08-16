"""Conservative temporary follow-up sessions keyed by group and user."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import RLock
from typing import Dict, Optional, Tuple


@dataclass
class GroupFollowupSession:
    """Short-lived permission for one member to continue a bot conversation."""

    group_id: str
    sender_id: str
    created_at: datetime
    last_bot_reply_at: Optional[datetime] = None
    followup_count: int = 0
    active: bool = True


class SessionManager:
    def __init__(
        self,
        timeout_seconds: float,
        max_followups: int = 2,
        break_on_other_user_message: bool = True,
    ) -> None:
        if timeout_seconds < 0:
            raise ValueError("timeout_seconds must not be negative")
        if max_followups < 1:
            raise ValueError("max_followups must be at least 1")
        self.timeout_seconds = timeout_seconds
        self.max_followups = max_followups
        self.break_on_other_user_message = break_on_other_user_message
        self._sessions: Dict[Tuple[str, str], GroupFollowupSession] = {}
        self._lock = RLock()

    @staticmethod
    def _now(now: Optional[datetime]) -> datetime:
        return now or datetime.now().astimezone()

    def get(self, group_key: str, sender_key: str) -> Optional[GroupFollowupSession]:
        with self._lock:
            return self._sessions.get((group_key, sender_key))

    def activate(
        self,
        group_key: str,
        sender_key: str,
        now: Optional[datetime] = None,
    ) -> GroupFollowupSession:
        """Create/reset a session after an explicit invocation produced a reply."""

        current = self._now(now)
        session = GroupFollowupSession(
            group_id=group_key,
            sender_id=sender_key,
            created_at=current,
            last_bot_reply_at=current,
            followup_count=0,
            active=True,
        )
        with self._lock:
            self._sessions[(group_key, sender_key)] = session
        return session

    def _expire_if_needed(self, session: GroupFollowupSession, current: datetime) -> bool:
        if not session.active or session.last_bot_reply_at is None:
            return True
        if current - session.last_bot_reply_at > timedelta(seconds=self.timeout_seconds):
            session.active = False
            return True
        if session.followup_count >= self.max_followups:
            session.active = False
            return True
        return False

    def can_followup(
        self,
        group_key: str,
        sender_key: str,
        now: Optional[datetime] = None,
    ) -> bool:
        current = self._now(now)
        with self._lock:
            started = self._sessions.get((group_key, sender_key))
            if started is None:
                return False
            if self._expire_if_needed(started, current):
                if started.last_bot_reply_at is not None and current - started.last_bot_reply_at > timedelta(seconds=self.timeout_seconds):
                    self._sessions.pop((group_key, sender_key), None)
                return False
            return True

    def is_active(self, group_key: str, sender_key: str, now: Optional[datetime] = None) -> bool:
        """Compatibility alias for callers that only need the follow-up gate."""

        return self.can_followup(group_key, sender_key, now)

    def record_followup(
        self,
        group_key: str,
        sender_key: str,
        now: Optional[datetime] = None,
    ) -> Optional[GroupFollowupSession]:
        """Record a successful no-mention response and close at the configured limit."""

        current = self._now(now)
        with self._lock:
            session = self._sessions.get((group_key, sender_key))
            if session is None or self._expire_if_needed(session, current):
                return None
            session.followup_count += 1
            session.last_bot_reply_at = current
            if session.followup_count >= self.max_followups:
                session.active = False
                self._sessions.pop((group_key, sender_key), None)
            return session

    def break_other_users(self, group_key: str, sender_key: str) -> int:
        """Invalidate other members' continuation permission in this group."""

        if not self.break_on_other_user_message:
            return 0
        invalidated = 0
        with self._lock:
            for (current_group, current_sender), session in list(self._sessions.items()):
                if current_group == group_key and current_sender != sender_key and session.active:
                    session.active = False
                    self._sessions.pop((current_group, current_sender), None)
                    invalidated += 1
        return invalidated

    def refresh(self, group_key: str, sender_key: str, now: Optional[datetime] = None) -> None:
        """Backward-compatible explicit reset; new routing uses activate/record_followup."""

        self.activate(group_key, sender_key, now)

    def clear(self, group_key: str, sender_key: Optional[str] = None) -> None:
        with self._lock:
            if sender_key is not None:
                self._sessions.pop((group_key, sender_key), None)
                return
            for key in [key for key in self._sessions if key[0] == group_key]:
                self._sessions.pop(key, None)
