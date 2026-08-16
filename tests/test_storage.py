from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from wechat_deepseek_bot.models import IncomingMessage
from wechat_deepseek_bot.storage.database import SQLiteStore


def msg(group="a", sender_id="u1", sender_name="Alice", content="hello", at=False, self_message=False, timestamp=None):
    return IncomingMessage(group, group, sender_id, sender_name, content, at, self_message, timestamp)


def test_archive_separates_groups_and_handles_quotes(tmp_path):
    store = SQLiteStore(tmp_path / "bot.sqlite3")
    store.archive_message(msg("a", content="O'Reilly says hi"))
    store.archive_message(msg("b", sender_id="u2", sender_name="Bob", content="other"))
    assert [row["content"] for row in store.recent_messages("a")] == ["O'Reilly says hi"]
    assert [row["sender_name"] for row in store.recent_messages("b")] == ["Bob"]


def test_retention_and_self_filter(tmp_path):
    store = SQLiteStore(tmp_path / "bot.sqlite3")
    old = datetime.now().astimezone() - timedelta(days=40)
    store.archive_message(msg(content="old", timestamp=old))
    store.archive_message(msg(content="self", self_message=True))
    store.cleanup(datetime.now().astimezone() - timedelta(days=30))
    assert store.recent_messages("a") == []
    assert store.recent_messages("a", include_self=True)[0]["content"] == "self"


def test_settings_and_delete_sender(tmp_path):
    store = SQLiteStore(tmp_path / "bot.sqlite3")
    store.set_settings("a", "gamer", 3)
    assert store.get_settings("a", "toxic_friend", 2) == {"persona": "gamer", "sarcasm_level": 3}
    store.archive_message(msg("a", sender_id="u1", content="mine"))
    store.archive_message(msg("a", sender_id="u2", sender_name="Bob", content="Bob's"))
    assert store.delete_sender("u1") == 1
    assert [row["sender_key"] for row in store.recent_messages("a")] == ["u2"]


def test_messages_between_uses_beijing_day_for_archives_with_other_offsets(tmp_path):
    store = SQLiteStore(tmp_path / "bot.sqlite3", "Asia/Shanghai")
    utc = ZoneInfo("UTC")
    store.archive_message(msg(content="before", timestamp=datetime(2026, 1, 31, 15, 59, tzinfo=utc)))
    store.archive_message(msg(content="first", timestamp=datetime(2026, 1, 31, 16, 0, tzinfo=utc)))
    store.archive_message(msg(content="last", timestamp=datetime(2026, 2, 1, 15, 59, tzinfo=utc)))
    store.archive_message(msg(content="after", timestamp=datetime(2026, 2, 1, 16, 0, tzinfo=utc)))

    beijing = ZoneInfo("Asia/Shanghai")
    messages = store.messages_between(
        "a",
        datetime(2026, 2, 1, 0, 0, tzinfo=beijing),
        datetime(2026, 2, 2, 0, 0, tzinfo=beijing),
        limit=1000,
    )

    assert [item["content"] for item in messages] == ["first", "last"]
