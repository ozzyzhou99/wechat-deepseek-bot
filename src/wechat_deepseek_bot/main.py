"""Application bootstrap and graceful shutdown."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

from .bot.commands import CommandHandler, V2CommandHandler
from .bot.engine import BotEngine
from .bot.router import MessageRouter
from .config import ConfigError, load_config
from .content_filter import DeepSeekPoliticsClassifier, PoliticsFilter
from .llm.deepseek import DeepSeekClient
from .memory.conversation import ConversationStore
from .features.manager import FeatureManager
from .games.manager import GameManager
from .persona.manager import PersonaManager
from .sessions import SessionManager
from .storage.database import SQLiteStore
from .utils.logging import configure_logging
from .wechat.factory import create_wechat_transport


def main(argv: Optional[Sequence[str]] = None) -> int:
    del argv
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"Configuration error: {exc}")
        return 2

    logger = configure_logging(config.log_level, Path("logs"))
    logger.info("starting WeChat DeepSeek bot")
    logger.info("starting transport-agnostic bot framework model=%s", config.deepseek_model)

    try:
        llm = DeepSeekClient(
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
            model=config.deepseek_model,
            temperature=config.llm_temperature,
            max_tokens=config.llm_max_tokens,
            timeout_seconds=config.llm_timeout_seconds,
            logger=logger,
        )
        politics_classifier = (
            DeepSeekPoliticsClassifier(llm, logger=logger)
            if config.politics_filter_enabled and config.politics_filter_mode == "hybrid"
            else None
        )
        politics_filter = PoliticsFilter(
            enabled=config.politics_filter_enabled,
            mode=config.politics_filter_mode,
            reply=config.politics_filter_reply,
            classifier=politics_classifier,
            logger=logger,
        )
        store = ConversationStore(config.context_max_turns)
        archive_store = SQLiteStore(config.database_path, config.app_timezone)
        if config.chat_archive_enabled:
            archive_store.cleanup(
                datetime.now(ZoneInfo(config.app_timezone)) - timedelta(days=config.chat_archive_retention_days)
            )
        persona_manager = PersonaManager(
            archive_store,
            default_name=config.persona,
            default_sarcasm=config.sarcasm_level,
            casual_max_sentences=config.casual_max_sentences,
        )
        sessions = SessionManager(
            config.group_no_mention_followup_seconds,
            max_followups=config.group_no_mention_max_followups,
            break_on_other_user_message=config.group_break_session_on_other_user_message,
        )
        games = GameManager() if config.games_enabled else None
        features = FeatureManager(
            archive_store,
            persona_manager,
            config.app_timezone,
            config.chat_archive_max_summary_messages,
        )
        commands = V2CommandHandler(
            CommandHandler(store, config.deepseek_model, "authorized_adapter"),
            features,
            games,
            sessions,
        )
        engine = BotEngine(
            router=MessageRouter(config.reply_only_when_at, config.bot_display_name),
            store=store,
            command_handler=commands,
            llm=llm,
            logger=logger,
            archive=archive_store if config.chat_archive_enabled else None,
            sessions=sessions,
            persona_manager=persona_manager,
            games=games,
            ambient_reply_enabled=config.ambient_reply_enabled,
            politics_filter=politics_filter,
        )
        adapter = create_wechat_transport(config, engine, logger)
        commands.base.set_transport(adapter)
        adapter.run()
    except KeyboardInterrupt:
        logger.info("shutdown requested")
    except Exception:
        logger.exception("bot stopped because startup/runtime failed")
        return 1
    finally:
        logging.shutdown()
    return 0
