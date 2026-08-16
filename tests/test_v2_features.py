from types import SimpleNamespace

from wechat_deepseek_bot.features.manager import FeatureManager
from wechat_deepseek_bot.games.manager import GameManager
from wechat_deepseek_bot.models import ChatMessage, IncomingMessage
from wechat_deepseek_bot.persona.manager import PersonaManager
from wechat_deepseek_bot.storage.database import SQLiteStore


class FakeLLM:
    def __init__(self, answer="有用的总结"):
        self.answer = answer
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        return self.answer


def message(sender="Alice", sender_id="u1", content="x"):
    return IncomingMessage("group", "Group", sender_id, sender, content, True, False)


def setup(tmp_path):
    store = SQLiteStore(tmp_path / "bot.sqlite3")
    persona = PersonaManager(store)
    return store, FeatureManager(store, persona, "America/New_York"), GameManager()


def test_fun_and_stats_commands_are_local(tmp_path):
    store, features, _ = setup(tmp_path)
    store.archive_message(message(content="Apex") )
    store.archive_message(message(sender="Bob", sender_id="u2", content="Apex again"))
    assert "🎲" in features.handle("/roll 6", message(), FakeLLM())
    assert "消息数" in features.handle("/活跃榜", message(), FakeLLM())
    assert "apex" in features.handle("/热词", message(), FakeLLM()).lower()


def test_stats_never_exposes_a_raw_wechat_id(tmp_path):
    store, features, _ = setup(tmp_path)
    store.archive_message(message(sender="wxid_very_private_id", sender_id="wxid_very_private_id"))
    result = features.handle("/活跃榜", message(), FakeLLM())
    assert "wxid_very_private_id" not in result
    assert "群友·e_id" in result


def test_summary_uses_archived_messages_and_mocked_llm(tmp_path):
    store, features, _ = setup(tmp_path)
    store.archive_message(message(content="今天讨论了项目"))
    llm = FakeLLM("真实总结")
    assert features.handle("/总结 10", message(), llm) == "真实总结"
    assert llm.calls
    assert any(isinstance(item, ChatMessage) for item in llm.calls[0])


def test_today_summary_is_capped_at_1000_messages(tmp_path):
    store, features, _ = setup(tmp_path)
    features.max_summary_messages = 5000
    captured = {}

    def messages_between(group_id, start, end, limit):
        captured.update(group_id=group_id, limit=limit)
        return []

    store.messages_between = messages_between
    features._today("group")

    assert captured == {"group_id": "group", "limit": 1000}


def test_games_are_group_isolated_and_number_game_finishes(tmp_path):
    _, _, games = setup(tmp_path)
    llm = FakeLLM()
    assert "猜数字" in games.handle("/猜数字", message(), llm)
    assert games.is_active("group")
    assert not games.is_active("other")
    assert "游戏结束" in games.handle("/退出游戏", message(), llm)


def test_turtle_soup_hides_solution_until_answer(tmp_path):
    _, _, games = setup(tmp_path)
    llm = FakeLLM("无关")
    start = games.handle("/海龟汤", message(), llm)
    assert "答案：" not in start
    assert games.handle("是不是外星人？", message(), llm) == "无关"
    revealed = games.handle("/答案", message(), llm)
    assert revealed.startswith("答案：")
