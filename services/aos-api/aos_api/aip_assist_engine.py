"""Phase 3 · AIP Assist 引擎.

提供 Copilot 欢迎语、建议问题、对话历史 和 SSE 流式聊天。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()


# ── 权限感知标签 ──
_ROLE_TAGS: dict[str, list[str]] = {
    "viewer": ["faq", "guidance"],
    "analyst": ["faq", "guidance", "data-query", "report"],
    "admin": ["faq", "guidance", "data-query", "report", "config", "deploy"],
}


def _role_tags(role: str) -> list[str]:
    return _ROLE_TAGS.get(role, _ROLE_TAGS["viewer"])


# ── 对话消息 ──
class ChatMessage(BaseModel):
    role: str = "user"  # user | assistant | system
    content: str = ""
    timestamp: float = Field(default_factory=lambda: time.time())


class Conversation(BaseModel):
    id: str = Field(default_factory=lambda: "aip-conv-" + uuid.uuid4().hex[:8])
    title: str = ""
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


# ── 模拟回复语料 ──
_FAQ_REPLIES: list[str] = [
    "根据平台监控数据，当前 12 个数据流的健康状态为 100% 正常，其中 3 个增量同步任务平均延迟低于 5 秒。",
    "建议先检查数据源连接的最新握手时间，若超过 30 分钟未刷新，可触发一次手动同步以恢复增量管道。",
    "本 Ontology 包含 47 个对象类型，其中 8 个启用了 L4 自动化。你可以在「治理 → 角色」中查看权限映射。",
    "已为你生成报告草稿，覆盖最近 7 天的 SLA 指标，请前往「草稿审查」页面确认发布。",
    "检测到 2 条 ETL 逻辑可能受 schema 漂移影响，建议在合并前运行影响分析。",
]


class AssistEngine:
    """Copilot Assist 引擎。Singleton + threading.Lock。"""

    _instance: "AssistEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "AssistEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._conversations: dict[str, Conversation] = {}
                    cls._instance._suggestions: list[dict[str, Any]] = []
                    cls._instance._welcome: str = ""
                    cls._instance._init_defaults()
        return cls._instance

    # ── 内置默认值 ──
    def _init_defaults(self) -> None:
        self._welcome = "你好！我是 AOS 平台 Copilot，可以帮你查询数据、诊断管道、生成报告。请问需要什么帮助？"
        self._suggestions = [
            {"id": "sg-001", "category": "data", "text": "今天有哪些数据流出现了延迟？"},
            {"id": "sg-002", "category": "data", "text": "帮我查看 Ontology「客户360」的对象列表"},
            {"id": "sg-003", "category": "build", "text": "Pipeline 「order-sync」最近的构建日志"},
            {"id": "sg-004", "category": "build", "text": "为什么昨天的增量任务失败了？"},
            {"id": "sg-005", "category": "report", "text": "生成本周数据健康报告"},
            {"id": "sg-006", "category": "report", "text": "对比上月与本月的 SLA 达成率"},
            {"id": "sg-007", "category": "config", "text": "如何为新人配置只读角色？"},
            {"id": "sg-008", "category": "config", "text": "查看当前 L4 自动化触发器列表"},
            {"id": "sg-009", "category": "governance", "text": "哪些对象包含敏感字段标记？"},
            {"id": "sg-010", "category": "governance", "text": "显示最近的审计日志"},
            {"id": "sg-011", "category": "ai", "text": "为这个数据集推荐合适的 ML 特征"},
            {"id": "sg-012", "category": "ai", "text": "Copilot 能帮我做哪些事？"},
        ]

    # ── Welcome ──
    def get_welcome(self, role: str = "viewer") -> dict[str, Any]:
        return {
            "message": self._welcome,
            "role": role,
            "tags": _role_tags(role),
        }

    def set_welcome(self, message: str) -> None:
        with _LOCK:
            self._welcome = message

    # ── Suggestions ──
    def list_suggestions(self, category: str | None = None) -> list[dict[str, Any]]:
        if category:
            return [s for s in self._suggestions if s["category"] == category]
        return list(self._suggestions)

    def add_suggestion(self, category: str, text: str) -> dict[str, Any]:
        with _LOCK:
            item = {"id": "sg-" + uuid.uuid4().hex[:8], "category": category, "text": text}
            self._suggestions.append(item)
            return item

    # ── Conversations ──
    def create_conversation(self, title: str = "") -> Conversation:
        with _LOCK:
            conv = Conversation(title=title or "New Conversation")
            self._conversations[conv.id] = conv
            return conv

    def get_conversation(self, conv_id: str) -> Conversation | None:
        return self._conversations.get(conv_id)

    def list_conversations(self, limit: int = 20) -> list[Conversation]:
        items = sorted(self._conversations.values(), key=lambda c: c.updated_at, reverse=True)
        return items[:limit]

    def add_message(self, conv_id: str, role: str, content: str) -> ChatMessage:
        with _LOCK:
            conv = self._conversations.get(conv_id)
            if conv is None:
                raise KeyError(f"Conversation {conv_id} not found")
            msg = ChatMessage(role=role, content=content)
            conv.messages.append(msg)
            conv.updated_at = time.time()
            return msg

    def delete_conversation(self, conv_id: str) -> bool:
        with _LOCK:
            return self._conversations.pop(conv_id, None) is not None

    # ── Chat (模拟流式 token) ──
    def generate_reply_tokens(self, user_input: str) -> list[str]:
        """根据用户输入返回模拟 token 列表。"""
        base = _FAQ_REPLIES[len(user_input) % len(_FAQ_REPLIES)]
        # 按句号/逗号切分为 token
        tokens: list[str] = []
        buf = ""
        for ch in base:
            buf += ch
            if ch in "，。、；！？":
                tokens.append(buf)
                buf = ""
        if buf:
            tokens.append(buf)
        return tokens

    def reset(self) -> None:
        with _LOCK:
            self._conversations.clear()
            self._init_defaults()


def get_engine() -> AssistEngine:
    return AssistEngine()
