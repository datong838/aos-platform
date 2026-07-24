"""W2-K · Ontology 管理增强：Edit History + Cleanup + Interface."""
from __future__ import annotations

import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ─────────────── #36 Edit History ───────────────

class EditEvent(BaseModel):
    id: str = Field(default_factory=lambda: _uid("evt"))
    target_type: str       # object_type / link_type / property / interface
    target_id: str
    action: str            # create / update / delete / publish
    author: str = ""
    timestamp: str = Field(default_factory=_now)
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    rolled_back: bool = False


class EditHistoryEngine:
    """编辑历史引擎：全局时间线 + 按作者合并 + 逐条回退。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[EditEvent] = []

    def record(self, event: EditEvent) -> EditEvent:
        with self._lock:
            self._events.append(event)
        return event

    def get(self, event_id: str) -> EditEvent:
        for e in self._events:
            if e.id == event_id:
                return e
        raise KeyError(f"事件 {event_id} 不存在")

    def list(
        self,
        *,
        target_type: str | None = None,
        author: str | None = None,
        target_id: str | None = None,
    ) -> list[EditEvent]:
        with self._lock:
            events = list(self._events)
        if target_type:
            events = [e for e in events if e.target_type == target_type]
        if author:
            events = [e for e in events if e.author == author]
        if target_id:
            events = [e for e in events if e.target_id == target_id]
        return events

    def rollback(self, event_id: str) -> EditEvent:
        """回退单个事件 — 标记为已回退，返回事件。"""
        with self._lock:
            for e in self._events:
                if e.id == event_id:
                    e.rolled_back = True
                    return e
        raise KeyError(f"事件 {event_id} 不存在")

    def rollback_by_author(self, author: str) -> list[EditEvent]:
        """按作者批量回退。"""
        rolled = []
        with self._lock:
            for e in self._events:
                if e.author == author and not e.rolled_back:
                    e.rolled_back = True
                    rolled.append(e)
        return rolled

    def timeline_merged_by_author(self) -> list[dict[str, Any]]:
        """按作者合并的时间线视图。"""
        merged: dict[str, list[EditEvent]] = {}
        with self._lock:
            for e in self._events:
                merged.setdefault(e.author, []).append(e)
        return [
            {
                "author": author,
                "eventCount": len(events),
                "firstEvent": events[0].timestamp,
                "lastEvent": events[-1].timestamp,
                "targets": list({e.target_id for e in events}),
                "rolledBackCount": sum(1 for e in events if e.rolled_back),
            }
            for author, events in sorted(merged.items(), key=lambda x: x[1][0].timestamp)
        ]

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


# ─────────────── #37 Cleanup ───────────────

class CleanupTag(str):
    DEPRECATED_DATE_PASSED = "deprecated_date_passed"
    RECYCLE_BIN_SOURCE = "recycle_bin_source"
    LONG_NO_UPDATE = "long_no_update"
    MISSING_DESCRIPTION = "missing_description"
    NAME_MATCHES_REGEX = "name_matches_regex"
    UNINDEXED = "unindexed"


_CLEANUP_REGEX = re.compile(r"(test|deprecated)", re.IGNORECASE)
_LONG_NO_UPDATE_DAYS = 90


class CleanupItem(BaseModel):
    resource_type: str        # object_type / link_type / property / interface
    resource_id: str
    name: str
    description: str = ""
    updated_at: str = ""
    deprecated_date: str | None = None
    is_recycle_bin: bool = False
    is_indexed: bool = True
    tags: list[str] = Field(default_factory=list)
    action: str = ""          # delay / deprecate / delete (applied)


class CleanupEngine:
    """清理工具引擎：扫描 + 三级操作 + 6 种标记。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # 注册的资源: (resource_type, resource_id) -> CleanupItem
        self._resources: dict[tuple[str, str], CleanupItem] = {}

    def register(self, item: CleanupItem) -> CleanupItem:
        with self._lock:
            self._resources[(item.resource_type, item.resource_id)] = item
        return item

    def scan(self, *, tags: list[str] | None = None) -> list[CleanupItem]:
        """扫描并返回带清理标记的资源。"""
        items = self._scan_all()
        if tags:
            items = [i for i in items if any(t in i.tags for t in tags)]
        return items

    def _scan_all(self) -> list[CleanupItem]:
        with self._lock:
            items = []
            for item in self._resources.values():
                tags = self._compute_tags(item)
                item.tags = tags
                items.append(item)
            return items

    def _compute_tags(self, item: CleanupItem) -> list[str]:
        tags = []
        now = datetime.now(timezone.utc)

        if item.deprecated_date:
            try:
                dep_date = datetime.fromisoformat(item.deprecated_date.replace("Z", "+00:00"))
                if dep_date < now:
                    tags.append(CleanupTag.DEPRECATED_DATE_PASSED)
            except (ValueError, AttributeError):
                pass

        if item.is_recycle_bin:
            tags.append(CleanupTag.RECYCLE_BIN_SOURCE)

        if item.updated_at:
            try:
                upd = datetime.fromisoformat(item.updated_at.replace("Z", "+00:00"))
                if (now - upd).days > _LONG_NO_UPDATE_DAYS:
                    tags.append(CleanupTag.LONG_NO_UPDATE)
            except (ValueError, AttributeError):
                pass

        if not item.description or not item.description.strip():
            tags.append(CleanupTag.MISSING_DESCRIPTION)

        if _CLEANUP_REGEX.search(item.name):
            tags.append(CleanupTag.NAME_MATCHES_REGEX)

        if not item.is_indexed:
            tags.append(CleanupTag.UNINDEXED)

        return tags

    def apply(self, resource_type: str, resource_id: str, action: str) -> CleanupItem:
        """对指定资源执行 delay/deprecate/delete。"""
        if action not in ("delay", "deprecate", "delete"):
            raise ValueError(f"无效操作: {action}（允许: delay/deprecate/delete）")
        with self._lock:
            key = (resource_type, resource_id)
            item = self._resources.get(key)
            if not item:
                raise KeyError(f"资源 {resource_type}/{resource_id} 不存在")
            item.action = action
            if action == "delete":
                del self._resources[key]
            return item

    def batch_apply(
        self,
        *,
        tag: str | None = None,
        action: str = "delay",
    ) -> list[CleanupItem]:
        """批量操作（按标记筛选）。"""
        items = self._scan_all()
        if tag:
            items = [i for i in items if tag in i.tags]
        results = []
        for item in items:
            try:
                result = self.apply(item.resource_type, item.resource_id, action)
                results.append(result)
            except (KeyError, ValueError):
                pass
        return results

    def reset(self) -> None:
        with self._lock:
            self._resources.clear()


# ─────────────── #32 Ontology Interface ───────────────

class OntologyInterface(BaseModel):
    id: str = Field(default_factory=lambda: _uid("iface"))
    name: str
    description: str = ""
    properties: list[dict[str, Any]] = Field(default_factory=list)
    extends: list[str] = Field(default_factory=list)
    implemented_by: list[str] = Field(default_factory=list)
    version: int = 1
    owner: str = ""
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class InterfaceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class InterfaceEngine:
    """Ontology 接口类型引擎：多态抽象 + extend/implement。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._interfaces: dict[str, OntologyInterface] = {}

    def create(self, iface: OntologyInterface) -> OntologyInterface:
        with self._lock:
            # 校验 extends 中的父接口存在
            for parent_id in iface.extends:
                if parent_id not in self._interfaces:
                    raise InterfaceError(
                        "PARENT_NOT_FOUND",
                        f"父接口 {parent_id} 不存在",
                    )
            self._interfaces[iface.id] = iface
        return iface

    def get(self, interface_id: str) -> OntologyInterface:
        iface = self._interfaces.get(interface_id)
        if not iface:
            raise InterfaceError("NOT_FOUND", f"接口 {interface_id} 不存在")
        return iface

    def list(self) -> list[OntologyInterface]:
        with self._lock:
            return list(self._interfaces.values())

    def update(self, interface_id: str, updates: dict[str, Any]) -> OntologyInterface:
        with self._lock:
            iface = self._interfaces.get(interface_id)
            if not iface:
                raise InterfaceError("NOT_FOUND", f"接口 {interface_id} 不存在")
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(iface, k, v)
            iface.updated_at = _now()
            return iface

    def delete(self, interface_id: str) -> bool:
        with self._lock:
            if interface_id not in self._interfaces:
                raise InterfaceError("NOT_FOUND", f"接口 {interface_id} 不存在")
            # 检查是否被其他接口继承
            for other in self._interfaces.values():
                if interface_id in other.extends:
                    raise InterfaceError(
                        "STILL_EXTENDED",
                        f"接口 {interface_id} 被 {other.id} 继承，无法删除",
                    )
            # 检查是否被 OT 实现
            iface = self._interfaces[interface_id]
            if iface.implemented_by:
                raise InterfaceError(
                    "STILL_IMPLEMENTED",
                    f"接口 {interface_id} 被 {len(iface.implemented_by)} 个 Object Type 实现，无法删除",
                )
            del self._interfaces[interface_id]
            return True

    def implement(self, interface_id: str, object_type: str) -> OntologyInterface:
        """Object Type 声明实现接口。"""
        with self._lock:
            iface = self._interfaces.get(interface_id)
            if not iface:
                raise InterfaceError("NOT_FOUND", f"接口 {interface_id} 不存在")
            if object_type not in iface.implemented_by:
                iface.implemented_by.append(object_type)
            iface.updated_at = _now()
            return iface

    def get_implementors(self, interface_id: str) -> list[str]:
        iface = self.get(interface_id)
        return list(iface.implemented_by)

    def get_effective_properties(self, interface_id: str) -> list[dict[str, Any]]:
        """获取接口的有效属性（含继承的父接口属性）。"""
        iface = self.get(interface_id)
        props = list(iface.properties)
        for parent_id in iface.extends:
            parent = self._interfaces.get(parent_id)
            if parent:
                props.extend(self.get_effective_properties(parent_id))
        return props

    def reset(self) -> None:
        with self._lock:
            self._interfaces.clear()


# ─────────────── 单例 ───────────────

_edit_engine: EditHistoryEngine | None = None
_cleanup_engine: CleanupEngine | None = None
_iface_engine: InterfaceEngine | None = None
_lock = threading.Lock()


def get_edit_engine() -> EditHistoryEngine:
    global _edit_engine
    if _edit_engine is None:
        with _lock:
            if _edit_engine is None:
                _edit_engine = EditHistoryEngine()
    return _edit_engine


def get_cleanup_engine() -> CleanupEngine:
    global _cleanup_engine
    if _cleanup_engine is None:
        with _lock:
            if _cleanup_engine is None:
                _cleanup_engine = CleanupEngine()
    return _cleanup_engine


def get_iface_engine() -> InterfaceEngine:
    global _iface_engine
    if _iface_engine is None:
        with _lock:
            if _iface_engine is None:
                _iface_engine = InterfaceEngine()
    return _iface_engine
