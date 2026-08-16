"""Built-in commands that do not call the LLM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..memory.conversation import ConversationStore


HELP_TEXT = """HH 使用手册

怎么聊天
• 在群里 @HH 后直接提问，例如：@HH 帮我想个周末计划
• HH 回复时会 @ 触发者。
• 一次 @ 唤醒后，同一位群友可在 90 秒内连续追问 2 次，无需重复 @；其他成员发言、超时或两次追问用完后，请再 @HH。

常用命令
/help              显示本手册
/status            查看机器人状态
/reset             清除本群 AI 对话上下文
/总结 [数量]       总结最近聊天，默认 50 条
/今日总结          总结今天的群聊（包含机器人启动前已同步的历史）
/名场面  /今日话题  /活跃榜  /热词
/锐评 [内容]  /roll [上限]  /随机群友  /今日人品

小游戏
/猜数字  /海龟汤  /二十问  /文字冒险
/答案  /退出游戏

说明
• 总结和统计只依据本群已同步的聊天记录；不要把密码、验证码或敏感隐私发到群里。
• 命令也建议 @HH 使用，避免误触发。"""
RESET_TEXT = "本群对话上下文已清除。"


@dataclass(frozen=True)
class CommandResult:
    response: str


class CommandHandler:
    def __init__(self, store: ConversationStore, model_name: str, transport_name: str = "wx4py", wechat_version: str = "") -> None:
        self.store = store
        self.model_name = model_name
        self.transport_name = transport_name
        self.wechat_version = wechat_version
        self.transport = None

    def set_transport(self, transport) -> None:
        self.transport = transport

    def handle(self, prompt: str, group_id: str) -> Optional[CommandResult]:
        command = prompt.strip().split(maxsplit=1)[0].lower() if prompt.strip() else ""
        if command == "/help":
            return CommandResult(HELP_TEXT)
        if command == "/reset":
            self.store.clear(group_id)
            return CommandResult(RESET_TEXT)
        if command == "/status":
            lines = [
                "Bot: online",
                f"Model: {self.model_name}",
                f"Context: {self.store.turn_count(group_id)}/{self.store.max_turns} turns",
            ]
            if self.transport is not None or self.transport_name != "wx4py":
                lines.append(f"Transport: {self.transport_name}")
                if self.transport_name == "hook":
                    online = bool(self.transport and self.transport.is_logged_in())
                    inbound = getattr(self.transport, "inbound_mode_selected", None) or "callback"
                    lines.extend((f"Hook: {'online' if online else 'offline'}", f"Inbound: {inbound}"))
                    if self.wechat_version:
                        lines.append(f"WeChat: {self.wechat_version}")
            return CommandResult("\n".join(lines))
        return None


V2_HELP_TEXT = HELP_TEXT + """

更多设置
/persona            查看当前人格及配置方式
/sarcasm            查看当前语气及配置方式
/忘掉我             删除你的群聊存档"""


class V2CommandHandler:
    """Compose stable V1 commands with separately testable V2 features."""

    def __init__(self, base: CommandHandler, features, games=None, sessions=None) -> None:
        self.base = base
        self.features = features
        self.games = games
        self.sessions = sessions

    def handle(self, prompt: str, message, llm) -> Optional[CommandResult]:
        command = prompt.strip().split(maxsplit=1)[0].lower() if prompt.strip() else ""
        if command == "/help":
            return CommandResult(V2_HELP_TEXT)
        result = self.base.handle(prompt, message.group_id)
        if result is not None:
            return result
        result_text = self.features.handle(prompt, message, llm)
        if result_text is not None:
            return CommandResult(result_text)
        if self.games is not None:
            result_text = self.games.handle(prompt, message, llm)
            if result_text is not None:
                return CommandResult(result_text)
        return None

    def handle_message(self, prompt: str, message, llm) -> Optional[CommandResult]:
        return self.handle(prompt, message, llm)
