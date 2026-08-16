"""Local, bounded analysis helpers for archived group messages."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, time, timedelta
from typing import Any, Dict, Iterable, List, Sequence
from zoneinfo import ZoneInfo


def local_day_bounds(timezone_name: str, now: datetime | None = None) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone_name)
    current = (now or datetime.now(zone)).astimezone(zone)
    start = datetime.combine(current.date(), time.min, tzinfo=zone)
    return start, start + timedelta(days=1)


def message_lines(messages: Sequence[Dict[str, Any]]) -> str:
    return "\n".join(
        f"[{item['timestamp']}] {item['sender_name']}: {item['content']}"
        for item in messages
    )


def statistics(messages: Sequence[Dict[str, Any]]) -> str:
    counts = Counter(item["sender_name"] or "unknown" for item in messages)
    lines = ["群消息统计：", f"消息数：{len(messages)}", f"活跃成员：{len(counts)}"]
    if counts:
        lines.append("\n活跃榜：")
        lines.extend(f"{index}. {_display_name(name)} — {count}" for index, (name, count) in enumerate(counts.most_common(10), 1))
    return "\n".join(lines)


def _display_name(value: str) -> str:
    """Never post a raw WeChat ID when a nickname was unavailable."""

    name = str(value or "unknown").strip()
    if name.startswith(("wxid_", "gh_", "openim_")):
        return f"群友·{name[-4:]}"
    return name


def hot_words(messages: Sequence[Dict[str, Any]], limit: int = 8) -> List[tuple[str, int]]:
    counts: Counter[str] = Counter()
    stopwords = {"这个", "那个", "我们", "你们", "可以", "不是", "然后", "还是", "就是", "什么"}
    for item in messages:
        content = item["content"].lower()
        tokens = re.findall(r"[\u4e00-\u9fff]{2,8}|[a-zA-Z][a-zA-Z0-9_-]{2,}|\d+", content)
        for token in tokens:
            if token not in stopwords:
                counts[token] += 1
    return counts.most_common(limit)


def highlights(messages: Sequence[Dict[str, Any]], limit: int = 3) -> str:
    if not messages:
        return "最近没有足够的聊天记录，名场面暂时空缺。"
    # Only quote exact archived content; ranking is local and deliberately simple.
    ranked = sorted(messages, key=lambda item: (len(item["content"]), item["timestamp"]), reverse=True)
    chosen = ranked[:limit]
    lines = ["最近名场面（原话摘录）："]
    for index, item in enumerate(chosen, 1):
        lines.append(f"{index}. {item['sender_name']}：{item['content']}")
    return "\n".join(lines)


def today_topics(messages: Sequence[Dict[str, Any]], limit: int = 5) -> str:
    words = hot_words(messages, limit)
    if not words:
        return "今天还没聊出什么主题。"
    return "今天主要聊了：\n" + "\n".join(f"{index}. {word}" for index, (word, _) in enumerate(words, 1))
