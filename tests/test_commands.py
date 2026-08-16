from wechat_deepseek_bot.bot.commands import CommandHandler
from wechat_deepseek_bot.memory.conversation import ConversationStore


def test_help_command():
    store = ConversationStore()
    result = CommandHandler(store, "deepseek-v4-flash").handle("/help", "group-a")
    assert result is not None
    assert "/reset" in result.response


def test_reset_only_clears_current_group():
    store = ConversationStore()
    store.append_user("a", "one")
    store.append_assistant("a", "two")
    store.append_user("b", "three")
    store.append_assistant("b", "four")
    result = CommandHandler(store, "deepseek-v4-flash").handle("/reset", "a")
    assert result.response
    assert store.get_history("a") == []
    assert len(store.get_history("b")) == 2


def test_status_does_not_expose_secrets():
    store = ConversationStore()
    store.append_user("a", "one")
    store.append_assistant("a", "two")
    result = CommandHandler(store, "deepseek-v4-flash").handle("/status", "a")
    assert result.response == "Bot: online\nModel: deepseek-v4-flash\nContext: 1/10 turns"
    assert "API" not in result.response
