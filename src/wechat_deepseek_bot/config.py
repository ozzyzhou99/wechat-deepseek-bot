"""Environment-backed configuration for the transport-agnostic framework."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

from .content_filter import DEFAULT_POLITICS_FILTER_REPLY


class ConfigError(ValueError):
    """Raised when the supplied configuration is invalid."""


@dataclass(frozen=True)
class AppConfig:
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    llm_temperature: float
    llm_max_tokens: int
    llm_timeout_seconds: float
    bot_display_name: str
    reply_only_when_at: bool
    context_max_turns: int
    log_level: str
    persona: str = "toxic_friend"
    sarcasm_level: int = 3
    casual_max_sentences: int = 3
    group_no_mention_followup_seconds: float = 90
    group_no_mention_max_followups: int = 2
    group_break_session_on_other_user_message: bool = True
    ambient_reply_enabled: bool = False
    chat_archive_enabled: bool = False
    chat_archive_retention_days: int = 1
    chat_archive_max_summary_messages: int = 1000
    app_timezone: str = "Asia/Shanghai"
    games_enabled: bool = True
    database_path: str = "data/bot.sqlite3"
    politics_filter_enabled: bool = True
    politics_filter_mode: str = "hybrid"
    politics_filter_reply: str = DEFAULT_POLITICS_FILTER_REPLY


def _get(env: Mapping[str, str], name: str, default: str = "") -> str:
    return env.get(name, default).strip()


def _parse_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = _get(env, name, str(default)).lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be a boolean (true/false), got {raw!r}")


def _parse_int(env: Mapping[str, str], name: str, default: int, minimum: int = 1) -> int:
    raw = _get(env, name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc
    if value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}")
    return value


def _parse_float(env: Mapping[str, str], name: str, default: float, minimum: float = 0.0) -> float:
    raw = _get(env, name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from exc
    if value < minimum:
        raise ConfigError(f"{name} must be at least {minimum}")
    return value


def load_config(env: Optional[Mapping[str, str]] = None, dotenv_path: Optional[Path] = None) -> AppConfig:
    """Load configuration without logging credentials or channel identifiers."""

    if env is None:
        load_dotenv(dotenv_path=dotenv_path)
        env = os.environ

    api_key = _get(env, "DEEPSEEK_API_KEY")
    if not api_key:
        raise ConfigError("DEEPSEEK_API_KEY is required")
    log_level = _get(env, "LOG_LEVEL", "INFO").upper()
    if log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ConfigError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    sarcasm_level = _parse_int(env, "SARCASM_LEVEL", 3, minimum=0)
    if sarcasm_level > 3:
        raise ConfigError("SARCASM_LEVEL must be between 0 and 3")
    app_timezone = _get(env, "APP_TIMEZONE", "Asia/Shanghai")
    try:
        ZoneInfo(app_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ConfigError(f"APP_TIMEZONE is not a valid IANA timezone: {app_timezone!r}") from exc
    politics_filter_mode = _get(env, "POLITICS_FILTER_MODE", "hybrid").lower()
    if politics_filter_mode not in {"off", "keywords", "hybrid"}:
        raise ConfigError("POLITICS_FILTER_MODE must be off, keywords, or hybrid")

    return AppConfig(
        deepseek_api_key=api_key,
        deepseek_base_url=_get(env, "DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=_get(env, "DEEPSEEK_MODEL", "deepseek-v4-flash"),
        llm_temperature=_parse_float(env, "LLM_TEMPERATURE", 0.7),
        llm_max_tokens=_parse_int(env, "LLM_MAX_TOKENS", 1500),
        llm_timeout_seconds=_parse_float(env, "LLM_TIMEOUT_SECONDS", 60.0),
        bot_display_name=_get(env, "BOT_DISPLAY_NAME"),
        reply_only_when_at=_parse_bool(env, "REPLY_ONLY_WHEN_AT", True),
        context_max_turns=_parse_int(env, "CONTEXT_MAX_TURNS", 10),
        log_level=log_level,
        persona=_get(env, "PERSONA", "toxic_friend"),
        sarcasm_level=sarcasm_level,
        casual_max_sentences=_parse_int(env, "CASUAL_MAX_SENTENCES", 3),
        group_no_mention_followup_seconds=_parse_float(env, "GROUP_NO_MENTION_FOLLOWUP_SECONDS", 90.0),
        group_no_mention_max_followups=_parse_int(env, "GROUP_NO_MENTION_MAX_FOLLOWUPS", 2),
        group_break_session_on_other_user_message=_parse_bool(env, "GROUP_BREAK_SESSION_ON_OTHER_USER_MESSAGE", True),
        ambient_reply_enabled=_parse_bool(env, "AMBIENT_REPLY_ENABLED", False),
        chat_archive_enabled=_parse_bool(env, "CHAT_ARCHIVE_ENABLED", False),
        chat_archive_retention_days=_parse_int(env, "CHAT_ARCHIVE_RETENTION_DAYS", 1),
        chat_archive_max_summary_messages=_parse_int(env, "CHAT_ARCHIVE_MAX_SUMMARY_MESSAGES", 1000),
        app_timezone=app_timezone,
        games_enabled=_parse_bool(env, "GAMES_ENABLED", True),
        database_path=_get(env, "CHAT_ARCHIVE_PATH", "data/bot.sqlite3"),
        politics_filter_enabled=_parse_bool(env, "POLITICS_FILTER_ENABLED", True),
        politics_filter_mode=politics_filter_mode,
        politics_filter_reply=_get(env, "POLITICS_FILTER_REPLY", DEFAULT_POLITICS_FILTER_REPLY),
    )
