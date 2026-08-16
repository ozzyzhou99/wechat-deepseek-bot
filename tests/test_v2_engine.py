from wechat_deepseek_bot.bot.commands import CommandHandler, V2CommandHandler
from wechat_deepseek_bot.bot.engine import BotEngine
from wechat_deepseek_bot.bot.router import MessageRouter
from wechat_deepseek_bot.features.manager import FeatureManager
from wechat_deepseek_bot.games.manager import GameManager
from wechat_deepseek_bot.memory.conversation import ConversationStore
from wechat_deepseek_bot.models import ChatMessage, IncomingMessage
from wechat_deepseek_bot.persona.manager import PersonaManager
from wechat_deepseek_bot.sessions import SessionManager
from wechat_deepseek_bot.storage.database import SQLiteStore


class FakeLLM:
    def __init__(self):
        self.calls = []

    def chat(self, messages):
        self.calls.append(list(messages))
        return "收到，继续说。"


def make_message(content, sender="Alice", sender_id="u1", at=False):
    return IncomingMessage("g", "Group", sender_id, sender, content, at, False)


def make_engine(tmp_path):
    archive = SQLiteStore(tmp_path / "bot.sqlite3")
    memory = ConversationStore()
    persona = PersonaManager(archive)
    sessions = SessionManager(300)
    features = FeatureManager(archive, persona, "America/New_York")
    llm = FakeLLM()
    commands = V2CommandHandler(CommandHandler(memory, "deepseek-v4-flash"), features, GameManager())
    engine = BotEngine(
        MessageRouter(True, "HH"), memory, commands, llm,
        archive=archive, sessions=sessions, persona_manager=persona, games=commands.games,
    )
    return engine, archive, llm


def test_v2_engine_archives_activates_and_limits_followup_to_user(tmp_path):
    engine, archive, llm = make_engine(tmp_path)
    assert engine.handle(make_message("@HH 你好", at=True)) == "收到，继续说。"
    assert engine.handle(make_message("那你再说一句", at=False)) == "收到，继续说。"
    assert engine.handle(make_message("我不是激活者", sender="Bob", sender_id="u2", at=False)) is None
    assert len(archive.recent_messages("g", 20)) == 3
    assert len(llm.calls) == 2


def test_v2_command_does_not_enter_normal_llm_memory(tmp_path):
    engine, archive, llm = make_engine(tmp_path)
    result = engine.handle(make_message("@HH /persona gentle", at=True))
    assert ".env" in result
    assert "重启" in result
    assert "toxic_friend" in engine.persona_manager.get("g")["name"]
    assert llm.calls == []


def test_v2_does_not_share_followup_session_when_sender_identity_is_missing(tmp_path):
    engine, archive, llm = make_engine(tmp_path)
    assert engine.handle(make_message("@HH 你好", sender="unknown", sender_id=None, at=True)) == "收到，继续说。"
    assert engine.handle(make_message("继续说", sender="unknown", sender_id=None, at=False)) is None
    assert len(llm.calls) == 1


def test_v2_uses_sender_nickname_when_transport_provides_one(tmp_path):
    engine, archive, llm = make_engine(tmp_path)
    assert engine.handle(make_message("@HH 你好", sender="Alice", sender_id=None, at=True)) == "收到，继续说。"
    assert engine.handle(make_message("继续说", sender="Alice", sender_id=None, at=False)) == "收到，继续说。"
    assert engine.handle(make_message("我不是 Alice", sender="Bob", sender_id=None, at=False)) is None
    assert len(llm.calls) == 2
