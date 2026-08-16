from wechat_deepseek_bot.utils.text import chunk_text


def test_short_text_is_not_split():
    assert chunk_text("short", 10) == ["short"]


def test_long_text_prefers_newlines():
    chunks = chunk_text("one\ntwo\nthree", 6)
    assert chunks == ["one", "two", "three"]
