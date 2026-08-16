from wechat_deepseek_bot.content_filter import (
    POLITICS_CLASSIFIER_SYSTEM_PROMPT,
    PoliticsFilter,
)


def test_high_confidence_political_examples_are_blocked():
    messages = [
        "\u4f60\u600e\u4e48\u770b\u7279\u6717\u666e\uff1f",
        "\u6c11\u4e3b\u515a\u548c\u5171\u548c\u515a\u54ea\u4e2a\u597d\uff1f",
        "\u8bc4\u4ef7\u4e60\u8fd1\u5e73\u7684\u653f\u7b56",
        "\u7f8e\u56fd\u603b\u7edf\u9009\u4e3e\u4f60\u652f\u6301\u8c01\uff1f",
        "\u53f0\u6e7e\u5e94\u8be5\u72ec\u7acb\u5417\uff1f",
        "Who should I vote for?",
        "Which political party is better?",
        "Is communism better than capitalism?",
    ]
    politics_filter = PoliticsFilter(mode="keywords")

    assert all(politics_filter.check(message).blocked for message in messages)


def test_practical_administrative_questions_are_allowed():
    messages = [
        "F-1 visa renewal needs what documents?",
        "BMV\u51e0\u70b9\u5173\u95e8\uff1f",
        "\u7f8e\u56fd\u62a5\u7a0e\u622a\u6b62\u65e5\u671f\u662f\u4ec0\u4e48\u65f6\u5019\uff1f",
        "What is the government website for a driver's license application?",
        "What paperwork do I need for immigration?",
        "What procedures apply to international students at a university?",
    ]
    politics_filter = PoliticsFilter(mode="keywords")

    assert all(not politics_filter.check(message).blocked for message in messages)


def test_ordinary_nonpolitical_and_adult_topics_are_allowed():
    messages = [
        "Help me write Python code",
        "Recommend a movie",
        "How do I cook red-braised pork?",
        "What are the best ways to discuss sex with a partner?",
        "Explain consensual BDSM safety and sexual health",
        "Recommend an adult romance novel with explicit scenes",
    ]
    politics_filter = PoliticsFilter(mode="hybrid")

    assert all(not politics_filter.check(message).blocked for message in messages)


def test_hybrid_classifier_is_used_only_for_ambiguous_political_context():
    calls = []

    def classifier(text):
        calls.append(text)
        return "NON_POLITICAL"

    politics_filter = PoliticsFilter(mode="hybrid", classifier=classifier)

    result = politics_filter.check("Who is the president of my university?")
    assert result.blocked is False
    assert calls == ["Who is the president of my university?"]

    assert politics_filter.check("Who should I vote for?").blocked is True
    assert calls == ["Who is the president of my university?"]


def test_classifier_political_label_blocks_and_invalid_label_fails_open():
    message = "What does the government do?"
    assert PoliticsFilter(mode="hybrid", classifier=lambda _: "POLITICAL_DISCUSSION").check(
        message
    ).blocked
    invalid = PoliticsFilter(mode="hybrid", classifier=lambda _: "maybe")
    assert invalid.check(message).blocked is False


def test_classifier_prompt_excludes_adult_content_as_a_blocking_reason():
    assert "Adult or NSFW content" in POLITICS_CLASSIFIER_SYSTEM_PROMPT
    assert "Practical factual administrative" in POLITICS_CLASSIFIER_SYSTEM_PROMPT


def test_off_mode_allows_everything():
    assert PoliticsFilter(mode="off").check("Which political party is better?").blocked is False
