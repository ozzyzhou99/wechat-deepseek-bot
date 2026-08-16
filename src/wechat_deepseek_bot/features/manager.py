"""V2 non-game commands: summaries, statistics, fun utilities, and settings."""

from __future__ import annotations

import random
from datetime import datetime
from typing import Optional

from ..llm.base import LLMClient, LLMError
from ..models import ChatMessage, IncomingMessage
from ..persona.manager import PersonaManager
from ..storage.database import SQLiteStore
from .analysis import highlights, local_day_bounds, message_lines, statistics, today_topics, hot_words


class FeatureManager:
    def __init__(
        self,
        store: SQLiteStore,
        persona: PersonaManager,
        timezone_name: str,
        max_summary_messages: int = 1000,
    ) -> None:
        self.store = store
        self.persona = persona
        self.timezone_name = timezone_name
        self.max_summary_messages = max_summary_messages

    @staticmethod
    def _command(prompt: str) -> tuple[str, str]:
        parts = prompt.strip().split(maxsplit=1)
        return (parts[0].lower(), parts[1].strip() if len(parts) > 1 else "") if parts else ("", "")

    def _today(self, group_id: str):
        start, end = local_day_bounds(self.timezone_name)
        return self.store.messages_between(group_id, start, end, min(self.max_summary_messages, 1000))

    def _summary(self, group_id: str, messages, llm: LLMClient, title: str) -> str:
        if not messages:
            return "这段时间群里没留下可总结的聊天记录。"
        prompt = f"""请用自然、简洁、像群友聊天的中文总结下面的群聊记录。
标题：{title}
只根据提供的记录，不得编造事实、决定、人物发言或引用。
优先提取真实主题、分歧、决定、未解决问题和有趣片段。
不要写客套开场，不要说“以下是总结”。

群聊记录：
{message_lines(messages)}"""
        try:
            return llm.chat([
                ChatMessage("system", "你是一个克制、准确的群聊总结员。"),
                ChatMessage("user", prompt),
            ])
        except (LLMError, Exception):
            return statistics(messages)

    def handle(self, prompt: str, message: IncomingMessage, llm: LLMClient) -> Optional[str]:
        command, argument = self._command(prompt)
        group_id = message.group_id
        if command in {"/总结", "/summary"}:
            limit = 50
            if argument.isdigit():
                limit = min(500, max(1, int(argument)))
            return self._summary(group_id, self.store.recent_messages(group_id, limit), llm, "最近群聊总结")
        if command in {"/今日总结", "/今日总結", "/today-summary"}:
            return self._summary(group_id, self._today(group_id), llm, "今日群聊总结")
        if command in {"/名场面", "/名場面", "/highlights"}:
            return highlights(self._today(group_id) or self.store.recent_messages(group_id, 50))
        if command in {"/今日话题", "/今日話題", "/topics"}:
            return today_topics(self._today(group_id))
        if command in {"/活跃榜", "/活躍榜", "/谁最水", "/誰最水", "/stats"}:
            return statistics(self._today(group_id) or self.store.recent_messages(group_id, 100))
        if command in {"/热词", "/熱詞", "/hotwords"}:
            words = hot_words(self._today(group_id) or self.store.recent_messages(group_id, 100))
            return "最近热词：\n" + ("\n".join(f"{word}（{count}）" for word, count in words) if words else "暂时没有明显热词。")
        if command in {"/roll", "/骰子"}:
            maximum = int(argument) if argument.isdigit() else 100
            maximum = min(1_000_000, max(1, maximum))
            return f"🎲 {random.randint(1, maximum)}"
        if command in {"/随机群友", "/隨機群友", "/random-member"}:
            names = sorted({item["sender_name"] for item in self.store.recent_messages(group_id, 200) if item["sender_name"] != "unknown"})
            return f"今天抽到：{random.choice(names)}" if names else "群里还没有足够的成员记录。"
        if command in {"/今日人品", "/今日人品"}:
            score = random.randint(1, 100)
            tone = "适合摸鱼" if score < 40 else "勉强能活" if score < 75 else "今天可以嚣张一下"
            return f"今日人品：{score}/100\n{tone}。仅供娱乐，别拿去买彩票。"
        if command in {"/锐评", "/銳評", "/roast"}:
            return self._roast(group_id, argument, message, llm)
        if command in {"/persona", "/人格"}:
            if not argument:
                current = self.persona.get(group_id)
                return f"当前 persona：{current['name']}\n可选：{', '.join(self.persona.names())}"
            return "人格设置由 .env 管理；修改 PERSONA 后重启机器人生效。"
        if command in {"/sarcasm", "/讽刺"}:
            if not argument.isdigit():
                return f"当前讽刺等级：{self.persona.get(group_id)['sarcasm_level']}（0-3）"
            return "语气设置由 .env 管理；修改 SARCASM_LEVEL 后重启机器人生效。"
        if command in {"/forgetme", "/忘掉我", "/忘記我"}:
            key = self.store.sender_key(message)
            deleted = self.store.delete_sender(key, None if message.sender_id else group_id)
            return "行，关于你的存档我清了。" if deleted else "我没有找到可以删除的个人存档。"
        return None

    def _roast(self, group_id: str, argument: str, message: IncomingMessage, llm: LLMClient) -> str:
        target = argument or message.sender_name
        messages = [item for item in self.store.recent_messages(group_id, 200) if target.lower() in item["sender_name"].lower()]
        if not messages:
            messages = self.store.recent_messages(group_id, 30)
        prompt = f"""请对群友“{target}”做一句到三句轻松、友善、基于事实的吐槽。
只能根据下面真实存档，不得编造经历、引入隐私或攻击敏感个人特征。
如果证据不足，就直接说证据不足，不要硬编。

真实消息：
{message_lines(messages)}"""
        try:
            return llm.chat([
                ChatMessage("system", "你是一个有分寸的群友吐槽助手。"),
                ChatMessage("user", prompt),
            ])
        except (LLMError, Exception):
            return f"关于 {target} 的素材还不够，先放你一马。"
