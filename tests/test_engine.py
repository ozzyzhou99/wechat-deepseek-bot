from wechat_deepseek_bot.bot.commands import CommandHandler
from wechat_deepseek_bot.bot.engine import BotEngine, TEMPORARY_ERROR_TEXT
from wechat_deepseek_bot.bot.router import MessageRouter
from wechat_deepseek_bot.memory.conversation import ConversationStore
from wechat_deepseek_bot.models import IncomingMessage
from wechat_deepseek_bot.llm.base import LLMError
from wechat_deepseek_bot.content_filter import PoliticsFilter


class FakeLLM:
    def __init__(self, answer="answer"):
        self.answer = answer
        self.calls = []

    def chat(self, messages):
        self.calls.append(list(messages))
        return self.answer


def msg(group="a", content="@Bot hello", at=True):
    return IncomingMessage(group, group, "s", "Alice", content, at, False)


def make_engine(llm, max_turns=10):
    store = ConversationStore(max_turns)
    return BotEngine(
        MessageRouter(True, "Bot"),
        store,
        CommandHandler(store, "deepseek-v4-flash"),
        llm,
    ), store


def test_engine_updates_context_after_success():
    llm = FakeLLM("hello back")
    engine, store = make_engine(llm)
    assert engine.handle(msg()) == "hello back"
    assert [item.content for item in store.get_history("a")] == ["hello", "hello back"]
    assert len(llm.calls) == 1
    assert llm.calls[0][-1].content == "hello"


def test_commands_do_not_call_llm():
    llm = FakeLLM()
    engine, _ = make_engine(llm)
    assert engine.handle(msg(content="@Bot /status"))
    assert llm.calls == []


def test_model_error_returns_safe_message():
    class BrokenLLM:
        def chat(self, messages):
            raise LLMError("private details")

    engine, store = make_engine(BrokenLLM())
    assert engine.handle(msg()) == TEMPORARY_ERROR_TEXT
    assert store.get_history("a") == []


def test_political_message_gets_fixed_reply_without_normal_llm_call():
    llm = FakeLLM()
    engine, store = make_engine(llm)
    engine.politics_filter = PoliticsFilter(mode="keywords", reply="politics blocked")

    assert engine.handle(msg(content="@Bot Which political party is better?")) == "politics blocked"
    assert llm.calls == []
    assert store.get_history("a") == []
