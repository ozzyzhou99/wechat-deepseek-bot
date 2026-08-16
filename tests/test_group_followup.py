from datetime import datetime, timedelta

from wechat_deepseek_bot.bot.commands import CommandHandler
from wechat_deepseek_bot.bot.engine import BotEngine
from wechat_deepseek_bot.bot.router import MessageRouter
from wechat_deepseek_bot.memory.conversation import ConversationStore
from wechat_deepseek_bot.models import IncomingMessage
from wechat_deepseek_bot.sessions import SessionManager


class FakeLLM:
    def __init__(self):
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return "reply"


def message(content, sender="Alice", sender_id="u1", at=False, group="g"):
    return IncomingMessage(group, group, sender_id, sender, content, at, False)


def make_engine(sessions):
    store = ConversationStore()
    llm = FakeLLM()
    engine = BotEngine(
        MessageRouter(True, "Bot"),
        store,
        CommandHandler(store, "model"),
        llm,
        sessions=sessions,
    )
    return engine, llm


def test_explicit_invocation_creates_sender_scoped_session():
    sessions = SessionManager(90, max_followups=2)
    engine, _ = make_engine(sessions)

    assert engine.handle(message("@Bot hello", at=True)) == "reply"
    session = sessions.get("g", "id:u1")
    assert session is not None
    assert session.followup_count == 0
    assert session.active is True
    assert session.last_bot_reply_at is not None


def test_two_followups_are_allowed_then_the_session_closes():
    sessions = SessionManager(90, max_followups=2)
    engine, llm = make_engine(sessions)

    assert engine.handle(message("@Bot question", at=True)) == "reply"
    assert engine.handle(message("follow-up 1")) == "reply"
    assert engine.handle(message("follow-up 2")) == "reply"
    assert engine.handle(message("follow-up 3")) is None
    assert len(llm.calls) == 3
    assert sessions.get("g", "id:u1") is None


def test_followup_sessions_expire_from_last_bot_reply():
    sessions = SessionManager(90)
    start = datetime.now().astimezone()
    sessions.activate("g", "id:u1", start)

    assert sessions.can_followup("g", "id:u1", start + timedelta(seconds=90))
    assert not sessions.can_followup("g", "id:u1", start + timedelta(seconds=90, microseconds=1))
    assert sessions.get("g", "id:u1") is None


def test_other_member_breaks_original_users_continuation():
    sessions = SessionManager(90, max_followups=2, break_on_other_user_message=True)
    engine, llm = make_engine(sessions)

    assert engine.handle(message("@Bot question", at=True)) == "reply"
    assert engine.handle(message("random group chat", sender="Bob", sender_id="u2")) is None
    assert engine.handle(message("another normal message")) is None
    assert len(llm.calls) == 1


def test_sessions_are_isolated_by_group_and_sender():
    sessions = SessionManager(90)
    engine, llm = make_engine(sessions)

    assert engine.handle(message("@Bot question", at=True, group="g1")) == "reply"
    assert engine.handle(message("wrong sender", sender="Bob", sender_id="u2", group="g1")) is None
    assert engine.handle(message("wrong group", group="g2")) is None
    assert len(llm.calls) == 1


def test_new_explicit_invocation_resets_followup_count():
    sessions = SessionManager(90, max_followups=2)
    engine, _ = make_engine(sessions)

    engine.handle(message("@Bot first", at=True))
    engine.handle(message("follow-up"))
    assert sessions.get("g", "id:u1").followup_count == 1
    engine.handle(message("@Bot new topic", at=True))
    assert sessions.get("g", "id:u1").followup_count == 0


def test_llm_error_does_not_create_or_refresh_session():
    class BrokenLLM:
        def chat(self, messages):
            raise RuntimeError("failure")

    sessions = SessionManager(90)
    store = ConversationStore()
    engine = BotEngine(
        MessageRouter(True, "Bot"),
        store,
        CommandHandler(store, "model"),
        BrokenLLM(),
        sessions=sessions,
    )

    assert engine.handle(message("@Bot hello", at=True))
    assert sessions.get("g", "id:u1") is None
