"""Persona selection, prompt construction, and human-like response guidance."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from ..storage.database import SQLiteStore
from .loader import load_personas


class PersonaManager:
    _CASUAL_RESPONSE_STYLES = (
        "直接回应：先给最有用的一句，只有确实需要时再补充背景。",
        "接话式回应：像在接住群友的话，可以先有一句自然反应，再进入重点；反应也可以省略。",
        "轻松解释：用一个自然的比喻、类比或生活化说法帮助理解，但不要为了俏皮而硬开玩笑。",
        "观点式回应：先给清楚判断，再说明一两个关键理由，不要自动写成完整小作文。",
        "互动式回应：如果问题有歧义或适合继续聊，可以自然地抛出一个具体追问；不需要时直接回答。",
        "极简回应：如果一句话已经说清楚，就停在一句话，不要为了凑长度加 emoji 或总结。",
    )

    def __init__(
        self,
        store: SQLiteStore,
        default_name: str = "toxic_friend",
        default_sarcasm: int = 3,
        directory: Optional[Path] = None,
        casual_max_sentences: int = 3,
    ) -> None:
        self.store = store
        self.default_name = default_name
        self.default_sarcasm = default_sarcasm
        self.casual_max_sentences = casual_max_sentences
        self.directory = directory or Path(__file__).with_name("personas")
        self.personas = load_personas(self.directory)
        if default_name not in self.personas:
            self.default_name = "toxic_friend" if "toxic_friend" in self.personas else next(iter(self.personas))

    def names(self) -> list[str]:
        return sorted(self.personas)

    def get(self, group_key: str) -> Dict[str, Any]:
        settings = self.store.get_settings(group_key, self.default_name, self.default_sarcasm)
        name = settings["persona"] if settings["persona"] in self.personas else self.default_name
        level = max(0, min(3, int(settings["sarcasm_level"])))
        return {"name": name, "sarcasm_level": level, "data": self.personas[name]}

    def set_persona(self, group_key: str, name: str) -> bool:
        if name not in self.personas:
            return False
        current = self.get(group_key)
        self.store.set_settings(group_key, name, current["sarcasm_level"])
        return True

    def set_sarcasm(self, group_key: str, level: int) -> bool:
        if level < 0 or level > 3:
            return False
        current = self.get(group_key)
        self.store.set_settings(group_key, current["name"], level)
        return True

    @staticmethod
    def _serious_mode(user_prompt: str) -> bool:
        lowered = user_prompt.lower()
        signals = (
            "```", "traceback", "报错", "代码", "公式", "计算", "解释",
            "python", "moran", "api", "sql", "论文", "怎么做", "为什么",
        )
        return len(user_prompt) > 45 or any(signal in lowered for signal in signals)

    @classmethod
    def _response_style(
        cls, group_key: str, user_prompt: str, mode: str, turn_index: int = 0
    ) -> str:
        """Pick a stable preference without turning it into a rigid template."""

        if mode == "serious/useful":
            return "清晰解题：先回答结论，再按问题复杂度补充步骤、例子或限制条件；需要结构时再使用分点。"
        digest = hashlib.blake2s(
            f"{group_key}\x00{turn_index}\x00{user_prompt}".encode("utf-8"), digest_size=2
        ).digest()
        return cls._CASUAL_RESPONSE_STYLES[int.from_bytes(digest, "big") % len(cls._CASUAL_RESPONSE_STYLES)]

    def system_prompt(
        self,
        group_key: str,
        user_prompt: str,
        base_prompt: str,
        turn_index: int = 0,
    ) -> str:
        selected = self.get(group_key)
        data = selected["data"]
        style = data.get("style", {})
        principles = data.get("principles", [])
        level = selected["sarcasm_level"]
        mode = "serious/useful" if self._serious_mode(user_prompt) else "casual/chatty"
        level_text = (
            "normal and friendly" if level == 0 else
            "light teasing" if level == 1 else
            "sarcastic friend" if level == 2 else
            "very cheeky but never hostile"
        )
        principles_text = "\n".join(f"- {item}" for item in principles)
        response_style = self._response_style(group_key, user_prompt, mode, turn_index)
        return f"""{base_prompt}

You are participating as a real member of a WeChat group, not customer support.
Selected persona: {selected['name']} — {data.get('description', '')}
Current response mode: {mode}.
Preferred expression shape for this turn: {response_style}
Sarcasm level: {level} ({level_text}).
Casual replies should usually fit within {self.casual_max_sentences} short sentences.
Style settings: {style}
Persona principles:
{principles_text}

Humanizer rules:
- Vary the shape of nearby replies: a direct answer, a brief reaction, a short explanation, a question back, or a few bullets when useful are all valid.
- Do not mechanically use “一句话 + emoji + 一句话”, and do not force exactly two sentences.
- Avoid canned openings, numbered advice lists, and formal wrap-ups unless the task genuinely needs structure.
- Do not say “if you have any other questions” or similar customer-service phrases by default.
- An emoji is optional. It may be absent, and if used it should fit the meaning rather than sit between two sentences as decoration.
- Match the user's energy and wording without copying a repetitive catchphrase. Natural pauses, short paragraphs, and occasional emphasis are fine.
- One short natural sentence or reaction is often enough in casual chat; a longer answer is fine when the question deserves it.
- Do not force a joke into every answer, and do not introduce fake typos.
- For serious or technical questions, prioritize accurate, useful content and keep jokes optional and brief.
- Never invent group memories, quotes, actions, sources, or facts.
- Tease harmless behavior and situations only; never target protected or sensitive personal traits.
"""
