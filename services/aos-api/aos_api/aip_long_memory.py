"""AIP 四层记忆引擎 (Working / Episodic / Semantic / Procedural).

升级原有的泛型 CRUD 记忆容器为四层认知记忆模型：
  - **Working** (工作记忆): 当前会话上下文，短生命周期，自动过期。
  - **Episodic** (情景记忆): 带时间戳的具体事件记录（如"用户问了X，系统返回了Y"）。
  - **Semantic** (语义记忆): 领域知识事实（如"栖月汇的 Order OT 有 6 个必填字段"）。
  - **Procedural** (程序记忆): 可复用操作模式 / 最佳实践（如"分析订单异常的标准流程"）。

向后兼容：保留 LongMemoryItem + LongMemoryEngine + get_engine()，
旧 API 路由无需改动。四层能力通过新的 MemoryLayer enum 和分层查询 API 暴露。
"""
from __future__ import annotations

import threading
import time
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

_MAX_ITEMS = 500  # 从 200 提升到 500 以容纳四层
_LOCK = threading.Lock()


class MemoryLayer(str, Enum):
    """四层记忆模型。"""

    WORKING = "working"        # 工作记忆：当前会话上下文
    EPISODIC = "episodic"      # 情景记忆：具体事件
    SEMANTIC = "semantic"      # 语义记忆：领域知识
    PROCEDURAL = "procedural"  # 程序记忆：操作模式


# Working 记忆的默认 TTL（秒）：30 分钟
_WORKING_TTL_SECONDS = 1800


class LongMemoryItem(BaseModel):
    """长期记忆管理 数据模型（升级：增加 layer 字段）。"""

    id: str = Field(default_factory=lambda: "aip-long-memory-" + uuid.uuid4().hex[:8])
    name: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    layer: str = MemoryLayer.SEMANTIC.value  # 默认语义层，向后兼容
    content: str = ""  # 结构化记忆正文（Markdown）
    object_type: str = ""  # 关联的本体对象类型（可选）
    tags: list[str] = Field(default_factory=list)
    expires_at: float | None = None  # 仅 Working 层使用，自动过期
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class LongMemoryEngine:
    """长期记忆管理 引擎。Singleton + threading.Lock。

    升级功能：
    - 四层分层 (Working / Episodic / Semantic / Procedural)
    - 分层查询 list_by_layer()
    - Working 层自动过期清理
    - 语义检索 search()
    """

    _instance: "LongMemoryEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "LongMemoryEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._items: dict[str, LongMemoryItem] = {}
        return cls._instance

    # ── 通用 CRUD（向后兼容）──

    def create(self, name: str, config: dict[str, Any] | None = None, **kwargs: Any) -> LongMemoryItem:
        with _LOCK:
            self._evict_expired()
            if len(self._items) >= _MAX_ITEMS:
                raise ValueError(f"已达容量上限 {_MAX_ITEMS}")
            # 兼容旧调用方式 create(name, config)
            layer = kwargs.get("layer", MemoryLayer.SEMANTIC.value)
            item = LongMemoryItem(
                name=name,
                config=config or {},
                layer=layer,
                content=kwargs.get("content", ""),
                object_type=kwargs.get("object_type", ""),
                tags=kwargs.get("tags", []),
                expires_at=kwargs.get("expires_at"),
            )
            # Working 层自动设过期
            if item.layer == MemoryLayer.WORKING.value and item.expires_at is None:
                item.expires_at = time.time() + _WORKING_TTL_SECONDS
            self._items[item.id] = item
            return item

    def get(self, item_id: str) -> LongMemoryItem | None:
        self._evict_expired()
        return self._items.get(item_id)

    def list(self) -> list[LongMemoryItem]:
        self._evict_expired()
        return list(self._items.values())

    def update(self, item_id: str, **kwargs: Any) -> LongMemoryItem:
        with _LOCK:
            item = self._items.get(item_id)
            if item is None:
                raise KeyError(f"不存在 {item_id}")
            for k, v in kwargs.items():
                if hasattr(item, k):
                    setattr(item, k, v)
            item.updated_at = time.time()
            return item

    def delete(self, item_id: str) -> bool:
        with _LOCK:
            return self._items.pop(item_id, None) is not None

    def reset(self) -> None:
        """清空引擎（测试隔离用）。"""
        with _LOCK:
            self._items.clear()

    # ── 四层分层查询 ──

    def list_by_layer(self, layer: str) -> list[LongMemoryItem]:
        """按记忆层筛选。"""
        self._evict_expired()
        return [item for item in self._items.values() if item.layer == layer]

    def list_working(self) -> list[LongMemoryItem]:
        """获取当前工作记忆（未过期的）。"""
        return self.list_by_layer(MemoryLayer.WORKING.value)

    def list_episodic(self) -> list[LongMemoryItem]:
        """获取情景记忆。"""
        return self.list_by_layer(MemoryLayer.EPISODIC.value)

    def list_semantic(self) -> list[LongMemoryItem]:
        """获取语义记忆。"""
        return self.list_by_layer(MemoryLayer.SEMANTIC.value)

    def list_procedural(self) -> list[LongMemoryItem]:
        """获取程序记忆。"""
        return self.list_by_layer(MemoryLayer.PROCEDURAL.value)

    # ── 语义检索 ──

    def search(self, query: str, layer: str | None = None) -> list[LongMemoryItem]:
        """简易关键词检索：在 name/content/tags 中匹配。

        Args:
            query: 搜索关键词（不区分大小写）。
            layer: 可选，限定在某一记忆层内搜索。
        """
        self._evict_expired()
        q = query.lower()
        results: list[LongMemoryItem] = []
        for item in self._items.values():
            if layer and item.layer != layer:
                continue
            searchable = f"{item.name} {item.content} {' '.join(item.tags)}".lower()
            if q in searchable:
                results.append(item)
        return results

    # ── 层统计 ──

    def layer_stats(self) -> dict[str, int]:
        """返回各层的记忆条数。"""
        self._evict_expired()
        stats: dict[str, int] = {}
        for layer in MemoryLayer:
            stats[layer.value] = sum(
                1 for item in self._items.values() if item.layer == layer.value
            )
        stats["total"] = len(self._items)
        return stats

    # ── 内部：过期清理 ──

    def _evict_expired(self) -> None:
        """清理已过期的 Working 层记忆。调用方需持有 _LOCK 或在只读路径。"""
        now = time.time()
        expired = [
            item_id
            for item_id, item in self._items.items()
            if item.expires_at is not None and item.expires_at < now
        ]
        for item_id in expired:
            self._items.pop(item_id, None)


def get_engine() -> LongMemoryEngine:
    return LongMemoryEngine()
