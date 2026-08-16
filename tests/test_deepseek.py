from types import SimpleNamespace

import pytest

from wechat_deepseek_bot.llm import deepseek
from wechat_deepseek_bot.llm.base import LLMError
from wechat_deepseek_bot.models import ChatMessage


class FakeCompletions:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


class FakeOpenAI:
    completions = None

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.chat = SimpleNamespace(completions=FakeOpenAI.completions)


def make_client(monkeypatch, response=None, error=None):
    FakeOpenAI.completions = FakeCompletions(response=response, error=error)
    monkeypatch.setattr(deepseek, "OpenAI", FakeOpenAI)
    client = deepseek.DeepSeekClient("secret", "https://api.deepseek.com", "deepseek-v4-flash", 0.7, 1500, 60)
    return client, FakeOpenAI.completions


def test_model_messages_and_text_are_extracted(monkeypatch):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=" answer "))]
    )
    client, calls = make_client(monkeypatch, response=response)
    answer = client.chat([ChatMessage("system", "system"), ChatMessage("user", "hello")])
    assert answer == "answer"
    assert calls.kwargs["model"] == "deepseek-v4-flash"
    assert calls.kwargs["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "hello"},
    ]


def test_api_exception_becomes_llm_error(monkeypatch):
    client, _ = make_client(monkeypatch, error=RuntimeError("network details"))
    with pytest.raises(LLMError):
        client.chat([ChatMessage("user", "hello")])


def test_empty_response_becomes_llm_error(monkeypatch):
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=" "))])
    client, _ = make_client(monkeypatch, response=response)
    with pytest.raises(LLMError):
        client.chat([ChatMessage("user", "hello")])
