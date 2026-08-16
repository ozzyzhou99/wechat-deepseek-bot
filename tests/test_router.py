from wechat_deepseek_bot.bot.router import MessageRouter, strip_bot_mention
from wechat_deepseek_bot.models import IncomingMessage


def message(content="hello", at=False, self_message=False):
    return IncomingMessage("id-a", "Group A", "sender", "Alice", content, at, self_message)


def test_ordinary_message_is_ignored():
    result = MessageRouter().route(message())
    assert result.accepted is False


def test_at_message_is_accepted_and_mention_removed():
    result = MessageRouter(bot_display_name="DeepBot").route(message("@DeepBot hello", at=True))
    assert result.accepted is True
    assert result.prompt == "hello"


def test_self_message_is_ignored():
    assert MessageRouter().route(message("@Bot hello", at=True, self_message=True)).accepted is False


def test_empty_message_and_empty_prompt_are_ignored():
    assert MessageRouter().route(message("   ", at=True)).accepted is False
    assert MessageRouter(bot_display_name="Bot").route(message("@Bot", at=True)).accepted is False


def test_mention_stripping_fallback():
    assert strip_bot_mention("@DeepBot\u2005 question", "DeepBot") == "question"
    assert strip_bot_mention("@DeepBot question") == "question"
