"""Small thread-safe SQLite store for group archive and settings."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo

from ..models import IncomingMessage


class SQLiteStore:
    def __init__(self, path: str | Path, timezone_name: str = "Asia/Shanghai") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.timezone_name = timezone_name
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.path), timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_key TEXT NOT NULL,
                    group_name TEXT NOT NULL,
                    sender_key TEXT NOT NULL,
                    sender_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    is_self INTEGER NOT NULL DEFAULT 0,
                    is_bot_mentioned INTEGER NOT NULL DEFAULT 0,
                    platform TEXT NOT NULL DEFAULT 'wechat',
                    platform_message_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_messages_group_time
                    ON messages(group_key, timestamp);
                CREATE INDEX IF NOT EXISTS idx_messages_sender
                    ON messages(group_key, sender_key, timestamp);
                CREATE TABLE IF NOT EXISTS group_settings (
                    group_key TEXT PRIMARY KEY,
                    persona TEXT NOT NULL,
                    sarcasm_level INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS transport_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS processed_platform_messages (
                    platform TEXT NOT NULL,
                    message_id TEXT NOT NULL,
                    processed_at TEXT NOT NULL,
                    PRIMARY KEY(platform, message_id)
                );
                """
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(messages)").fetchall()}
            if "platform" not in columns:
                connection.execute("ALTER TABLE messages ADD COLUMN platform TEXT NOT NULL DEFAULT 'wechat'")
            if "platform_message_id" not in columns:
                connection.execute("ALTER TABLE messages ADD COLUMN platform_message_id TEXT")
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_platform_id "
                "ON messages(platform, platform_message_id) WHERE platform_message_id IS NOT NULL"
            )

    def get_transport_state(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM transport_state WHERE key = ?", (key,)).fetchone()
        return str(row[0]) if row is not None else default

    def set_transport_state(self, key: str, value: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO transport_state(key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, datetime.now(ZoneInfo(self.timezone_name)).isoformat()),
            )

    def has_processed_platform_message(self, platform: str, message_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM processed_platform_messages WHERE platform = ? AND message_id = ?",
                (platform, message_id),
            ).fetchone()
        return row is not None

    def mark_processed_platform_message(self, platform: str, message_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO processed_platform_messages(platform, message_id, processed_at) VALUES (?, ?, ?)",
                (platform, message_id, datetime.now(ZoneInfo(self.timezone_name)).isoformat()),
            )

    @staticmethod
    def sender_key(message: IncomingMessage) -> str:
        return (message.sender_id or message.sender_name or "unknown").strip() or "unknown"

    def _timestamp(self, value: Optional[datetime]) -> str:
        return (value or datetime.now(ZoneInfo(self.timezone_name))).isoformat()

    def archive_message(self, message: IncomingMessage) -> None:
        if not message.content.strip():
            return
        with self._lock, self._connect() as connection:
            if message.message_id:
                existing = connection.execute(
                    "SELECT 1 FROM messages WHERE platform = ? AND platform_message_id = ?",
                    (message.platform, message.message_id),
                ).fetchone()
                if existing is not None:
                    # A later Hook import may resolve an older wxid-only entry to
                    # a local nickname. Preserve the stable sender key, but upgrade
                    # what group-facing features display.
                    if message.sender_name and not message.sender_name.startswith(("wxid_", "gh_", "openim_")):
                        connection.execute(
                            """
                            UPDATE messages SET sender_name = ?
                            WHERE platform = ? AND platform_message_id = ?
                              AND (sender_name LIKE 'wxid_%' OR sender_name LIKE 'gh_%' OR sender_name LIKE 'openim_%')
                            """,
                            (message.sender_name, message.platform, message.message_id),
                        )
                    return
            connection.execute(
                """
                INSERT INTO messages
                    (group_key, group_name, sender_key, sender_name, content,
                     timestamp, is_self, is_bot_mentioned, platform, platform_message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.group_id,
                    message.group_name,
                    self.sender_key(message),
                    message.sender_name or "unknown",
                    message.content,
                    self._timestamp(message.timestamp),
                    int(message.is_self),
                    int(message.is_at_bot),
                    message.platform,
                    message.message_id,
                ),
            )

    def recent_messages(self, group_key: str, limit: int = 50, include_self: bool = False) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 1000))
        predicate = "" if include_self else "AND is_self = 0"
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id, group_key, group_name, sender_key, sender_name, content,
                       timestamp, is_self, is_bot_mentioned
                FROM messages
                WHERE group_key = ? {predicate}
                ORDER BY id DESC
                LIMIT ?
                """,
                (group_key, safe_limit),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def messages_between(
        self,
        group_key: str,
        start: datetime,
        end: datetime,
        limit: int = 500,
        include_self: bool = False,
    ) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 1000))
        predicate = "" if include_self else "AND is_self = 0"
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT id, group_key, group_name, sender_key, sender_name, content,
                       timestamp, is_self, is_bot_mentioned
                FROM messages
                -- julianday compares absolute instants, so archives written with
                -- an older timezone setting still respect Beijing day boundaries.
                WHERE group_key = ? AND julianday(timestamp) >= julianday(?)
                  AND julianday(timestamp) < julianday(?) {predicate}
                ORDER BY id ASC
                LIMIT ?
                """,
                (group_key, start.isoformat(), end.isoformat(), safe_limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def cleanup(self, older_than: datetime) -> int:
        with self._lock, self._connect() as connection:
            cursor = connection.execute("DELETE FROM messages WHERE timestamp < ?", (older_than.isoformat(),))
            return cursor.rowcount

    def delete_sender(self, sender_key: str, group_key: Optional[str] = None) -> int:
        if not sender_key or sender_key == "unknown":
            return 0
        with self._lock, self._connect() as connection:
            if group_key:
                cursor = connection.execute(
                    "DELETE FROM messages WHERE sender_key = ? AND group_key = ?",
                    (sender_key, group_key),
                )
            else:
                cursor = connection.execute("DELETE FROM messages WHERE sender_key = ?", (sender_key,))
            return cursor.rowcount

    def get_settings(self, group_key: str, default_persona: str, default_sarcasm: int) -> Dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT persona, sarcasm_level FROM group_settings WHERE group_key = ?", (group_key,)
            ).fetchone()
        if row is None:
            return {"persona": default_persona, "sarcasm_level": default_sarcasm}
        return dict(row)

    def set_settings(self, group_key: str, persona: str, sarcasm_level: int) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO group_settings(group_key, persona, sarcasm_level)
                VALUES (?, ?, ?)
                ON CONFLICT(group_key) DO UPDATE SET
                    persona = excluded.persona,
                    sarcasm_level = excluded.sarcasm_level
                """,
                (group_key, persona, sarcasm_level),
            )

    def groups(self) -> Iterable[str]:
        with self._connect() as connection:
            rows = connection.execute("SELECT DISTINCT group_key FROM messages ORDER BY group_key").fetchall()
        return [row[0] for row in rows]
