from datetime import datetime, timedelta

from wechat_deepseek_bot.persona.manager import PersonaManager
from wechat_deepseek_bot.sessions import SessionManager
from wechat_deepseek_bot.storage.database import SQLiteStore


def test_persona_default_fallback_and_prompt(tmp_path):
    store = SQLiteStore(tmp_path / "bot.sqlite3")
    manager = PersonaManager(store, default_name="does_not_exist")
    assert manager.get("a")["name"] == "toxic_friend"
    prompt = manager.system_prompt("a", "Moran's I 怎么计算？", "base")
    assert "toxic_friend" in prompt
    assert "serious/useful" in prompt
    assert "Preferred expression shape for this turn" in prompt
    assert "emoji" in prompt


def test_persona_prompt_allows_multiple_natural_response_shapes(tmp_path):
    store = SQLiteStore(tmp_path / "bot.sqlite3")
    manager = PersonaManager(store)
    prompts = {
        manager.system_prompt("a", question, "base")
        for question in ("你好", "今天吃什么", "这个怎么理解", "笑死了", "你怎么看", "讲个冷知识")
    }
    assert len(prompts) >= 3
    combined = "\n".join(prompts)
    assert "Do not mechanically use" in combined
    assert "An emoji is optional" in combined


def test_persona_prompt_changes_casual_shape_across_turns(tmp_path):
    store = SQLiteStore(tmp_path / "bot.sqlite3")
    manager = PersonaManager(store)
    first = manager.system_prompt("a", "你好", "base", turn_index=0)
    second = manager.system_prompt("a", "你好", "base", turn_index=1)
    assert first != second


def test_persona_and_sarcasm_are_group_isolated(tmp_path):
    store = SQLiteStore(tmp_path / "bot.sqlite3")
    manager = PersonaManager(store)
    assert manager.set_persona("a", "gamer")
    assert manager.set_sarcasm("a", 3)
    assert manager.get("a")["name"] == "gamer"
    assert manager.get("a")["sarcasm_level"] == 3
    assert manager.get("b")["name"] == "toxic_friend"


def test_sessions_are_group_and_user_scoped_and_expire():
    manager = SessionManager(300)
    start = datetime.now().astimezone()
    manager.activate("a", "u1", start)
    assert manager.is_active("a", "u1", start + timedelta(seconds=10))
    assert not manager.is_active("a", "u2", start + timedelta(seconds=10))
    assert not manager.is_active("b", "u1", start + timedelta(seconds=10))
    assert not manager.is_active("a", "u1", start + timedelta(seconds=301))
