"""Small group-isolated games; only selected games call the existing LLM."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from ..llm.base import LLMClient, LLMError
from ..models import ChatMessage, IncomingMessage


PUZZLES = [
    {"title": "雨夜的灯", "surface": "一个人雨夜回家，看到窗内亮着灯，却立刻报警。为什么？", "solution": "那栋房子早已断电，亮灯说明有人非法进入。"},
    {"title": "电梯里的水", "surface": "一个人每天坐电梯到十楼，回家却只坐到七楼再走楼梯。晴天如此，雨天例外。为什么？", "solution": "他个子矮，晴天够不到十楼按钮；雨天用伞可以按到。"},
    {"title": "生日蜡烛", "surface": "生日宴上，寿星看到蜡烛就哭了，但大家都在祝贺。为什么？", "solution": "蜡烛数量代表他的年龄，他发现大家把年龄多算了一岁。"},
    {"title": "空房间的电话", "surface": "房间里没人，电话却响了。主人接起后说谢谢。为什么？", "solution": "他在等一个自动叫醒电话，电话让他知道时间到了。"},
    {"title": "最后一班车", "surface": "一个人赶上了最后一班车，却因此失去了工作。为什么？", "solution": "他是司机，赶上的最后一班车意味着他迟到了才发车。"},
]


@dataclass
class NumberGame:
    answer: int
    attempts: int = 0
    participants: set[str] = field(default_factory=set)


@dataclass
class TurtleGame:
    puzzle: dict


@dataclass
class TwentyGame:
    target: str
    questions: int = 0


@dataclass
class AdventureGame:
    summary: str = "你们站在一座雾里的旧城门前。"
    location: str = "旧城门"
    items: List[str] = field(default_factory=list)
    turn: int = 0


GameState = Union[NumberGame, TurtleGame, TwentyGame, AdventureGame]


class GameManager:
    def __init__(self) -> None:
        self._games: Dict[str, GameState] = {}

    def is_active(self, group_id: str) -> bool:
        return group_id in self._games

    def handle(self, prompt: str, message: IncomingMessage, llm: LLMClient) -> Optional[str]:
        command = prompt.strip().split(maxsplit=1)[0].lower() if prompt.strip() else ""
        argument = prompt.strip().split(maxsplit=1)[1].strip() if len(prompt.strip().split(maxsplit=1)) > 1 else ""
        group_id = message.group_id
        if command in {"/退出游戏", "/退出遊戲", "/quit-game"}:
            if self._games.pop(group_id, None) is None:
                return "当前没有进行中的游戏。"
            return "游戏结束，大家暂时保住了尊严。"
        if command in {"/猜数字", "/猜數字", "/number-guess"}:
            self._games[group_id] = NumberGame(random.randint(1, 100))
            return "猜数字开始：我想了一个 1-100 的数，来猜。"
        if command in {"/海龟汤", "/海龜湯", "/turtle-soup"}:
            puzzle = random.choice(PUZZLES)
            self._games[group_id] = TurtleGame(puzzle)
            return f"海龟汤《{puzzle['title']}》\n{puzzle['surface']}\n可以开始提问，答案用 /答案 揭晓。"
        if command in {"/二十问", "/二十問", "/twenty-questions"}:
            self._games[group_id] = TwentyGame(random.choice(["猫", "咖啡", "长城", "篮球", "企鹅", "月亮"]))
            return "二十问开始。我已经选好一个目标，只回答是/不是，最多 20 个问题。"
        if command in {"/文字冒险", "/文字冒險", "/adventure"}:
            self._games[group_id] = AdventureGame()
            return "文字冒险开始。\n你们站在一座雾里的旧城门前。\n可以输入：观察城门、向左走、敲门，或者自由行动。"
        if command in {"/答案", "/答案"}:
            game = self._games.get(group_id)
            if isinstance(game, TurtleGame):
                self._games.pop(group_id, None)
                return f"答案：{game.puzzle['solution']}"
            if isinstance(game, TwentyGame):
                self._games.pop(group_id, None)
                return f"答案是：{game.target}。问到这里，侦探证书先缓缓。"
            return "当前游戏没有可直接揭晓的答案。"

        game = self._games.get(group_id)
        if isinstance(game, NumberGame) and prompt.strip().lstrip("-").isdigit():
            guess = int(prompt.strip())
            game.attempts += 1
            game.participants.add(message.sender_id or message.sender_name or "unknown")
            if guess == game.answer:
                self._games.pop(group_id, None)
                return f"中了！答案就是 {game.answer}，用了 {game.attempts} 次。"
            return "大了。" if guess > game.answer else "小了。"
        if isinstance(game, TurtleGame) and prompt.strip() and not prompt.startswith("/"):
            return self._judge_turtle(game, prompt, llm)
        if isinstance(game, TwentyGame) and prompt.strip() and not prompt.startswith("/"):
            game.questions += 1
            if game.questions >= 20:
                self._games.pop(group_id, None)
                return f"20 个问题用完，答案是：{game.target}。"
            return self._judge_twenty(game, prompt, llm)
        if isinstance(game, AdventureGame) and prompt.strip() and not prompt.startswith("/"):
            return self._advance_adventure(game, prompt, llm)
        return None

    @staticmethod
    def _judge_turtle(game: TurtleGame, question: str, llm: LLMClient) -> str:
        prompt = f"""你是海龟汤裁判。根据表面故事和隐藏答案，判断玩家问题。
只能回复：是、不是、无关、部分正确。绝对不要透露隐藏答案。
表面：{game.puzzle['surface']}
隐藏答案：{game.puzzle['solution']}
玩家问题：{question}"""
        try:
            answer = llm.chat([ChatMessage("user", prompt)]).strip()
            return answer if answer in {"是", "不是", "无关", "部分正确"} else "无关"
        except (LLMError, Exception):
            return "这个问题我暂时判断不了。"

    @staticmethod
    def _judge_twenty(game: TwentyGame, question: str, llm: LLMClient) -> str:
        prompt = f"""你是二十问裁判。目标是“{game.target}”，玩家问题是“{question}”。
只回答“是”或“不是”，不要透露目标，不要解释。"""
        try:
            answer = llm.chat([ChatMessage("user", prompt)]).strip()
            return "是" if answer.startswith("是") else "不是"
        except (LLMError, Exception):
            return "裁判掉线了，先算无效一问。"

    @staticmethod
    def _advance_adventure(game: AdventureGame, action: str, llm: LLMClient) -> str:
        prompt = f"""你主持一个轻量中文文字冒险。
当前地点：{game.location}
物品：{', '.join(game.items) or '无'}
剧情摘要：{game.summary}
玩家行动：{action}
用 3-6 句推进剧情，给出 2-3 个可选行动，也接受自由行动。不要修改已有事实，不要让剧情无限膨胀。"""
        try:
            answer = llm.chat([ChatMessage("user", prompt)]).strip()
            game.turn += 1
            if len(answer) > 800:
                answer = answer[:800].rstrip() + "…"
            game.summary = (game.summary + " " + action + " " + answer)[-1500:]
            return answer
        except (LLMError, Exception):
            return "冒险主持人临时掉线了，刚才这步先当作没发生。"
