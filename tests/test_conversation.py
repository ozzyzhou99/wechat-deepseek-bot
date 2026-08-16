from wechat_deepseek_bot.memory.conversation import ConversationStore


def test_histories_are_separated_by_group():
    store = ConversationStore(max_turns=2)
    store.append_user("a", "A")
    store.append_assistant("a", "answer A")
    store.append_user("b", "B")
    store.append_assistant("b", "answer B")
    assert [item.content for item in store.get_history("a")] == ["A", "answer A"]
    assert [item.content for item in store.get_history("b")] == ["B", "answer B"]


def test_max_turns_is_bounded():
    store = ConversationStore(max_turns=2)
    for index in range(3):
        store.append_user("a", f"q{index}")
        store.append_assistant("a", f"a{index}")
    assert [item.content for item in store.get_history("a")] == ["q1", "a1", "q2", "a2"]


def test_clear_only_clears_one_group():
    store = ConversationStore()
    store.append_user("a", "A")
    store.append_assistant("a", "AA")
    store.append_user("b", "B")
    store.append_assistant("b", "BB")
    store.clear("a")
    assert store.get_history("a") == []
    assert len(store.get_history("b")) == 2
