"""W2-AA · 触发器与 Ontology 链接输出组（#97 / #98 / #91）.

- #97 EventTriggerEngine：dataset_updated / pipeline_built / schedule / manual 四种事件源 + fire 冷却期
- #98 CompositeTriggerEngine：AND / OR 逻辑组合 + evaluate + fire
- #91 LinkTypeOutputEngine：链接类型定义 CRUD + infer_from_objects + preview_links

详见 docs/palantier/20_tech/220tech_w2-aa-triggers-and-link-output.md。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

# ════════════════════ 常量 ════════════════════

_VALID_EVENT_SOURCES = {"dataset_updated", "pipeline_built", "schedule", "manual"}
_VALID_COMPOSITE_LOGICS = {"and", "or"}
_VALID_CARDINALITIES = {"one_to_many", "many_to_one", "many_to_many"}

_MAX_TRIGGERS = 200
_MAX_FIRES = 200
_MAX_COMPOSITES = 200
_MAX_LINKS = 200


# ════════════════════ 数据模型 ════════════════════

class EventTrigger(BaseModel):
    """事件触发器。"""
    id: str = Field(default_factory=lambda: "et-" + uuid.uuid4().hex[:10])
    name: str
    event_source: str
    target_pipeline_id: str
    source_ref: str = ""
    condition: str = ""
    enabled: bool = True
    cooldown_seconds: float = 0.0
    last_fired_at: float = 0.0
    fire_count: int = 0
    created_at: float = Field(default_factory=lambda: time.time())


class TriggerFire(BaseModel):
    """触发器点火记录。"""
    id: str = Field(default_factory=lambda: "tf-" + uuid.uuid4().hex[:10])
    trigger_id: str
    trigger_name: str = ""
    event_source: str = ""
    target_pipeline_id: str = ""
    event_payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "fired"          # fired / skipped / cooldown
    fired_at: float = Field(default_factory=lambda: time.time())


class CompositeTrigger(BaseModel):
    """复合触发器。"""
    id: str = Field(default_factory=lambda: "ct-" + uuid.uuid4().hex[:10])
    name: str
    logic: str                     # and / or
    child_trigger_ids: list[str]
    target_pipeline_id: str
    enabled: bool = True
    cooldown_seconds: float = 0.0
    last_fired_at: float = 0.0
    fire_count: int = 0
    created_at: float = Field(default_factory=lambda: time.time())


class LinkTypeDefinition(BaseModel):
    """Ontology 链接类型输出定义。"""
    id: str = Field(default_factory=lambda: "lt-" + uuid.uuid4().hex[:10])
    name: str
    display_name: str = ""
    cardinality: str               # one_to_many / many_to_one / many_to_many
    source_object_type: str
    target_object_type: str
    source_pk_field: str
    target_fk_field: str
    display_field: str = ""
    source_pipeline_id: str = ""
    description: str = ""
    created_at: float = Field(default_factory=lambda: time.time())


# ════════════════════ 错误 ════════════════════

class TriggersAndLinkOutputError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════ #97 EventTriggerEngine ════════════════════

class EventTriggerEngine:
    def __init__(self) -> None:
        self._triggers: dict[str, EventTrigger] = {}
        self._fires: list[TriggerFire] = []
        self._lock = threading.Lock()

    # ---- CRUD ----
    def register(self, trigger: EventTrigger) -> EventTrigger:
        if not trigger.name:
            raise TriggersAndLinkOutputError("MISSING_NAME", "触发器名称不能为空")
        if trigger.event_source not in _VALID_EVENT_SOURCES:
            raise TriggersAndLinkOutputError(
                "INVALID_EVENT_SOURCE",
                f"未知事件源：{trigger.event_source}",
            )
        if not trigger.target_pipeline_id:
            raise TriggersAndLinkOutputError(
                "MISSING_TARGET", "target_pipeline_id 不能为空",
            )
        with self._lock:
            if len(self._triggers) >= _MAX_TRIGGERS:
                # FIFO 淘汰最早一条
                oldest_id = next(iter(self._triggers))
                self._triggers.pop(oldest_id, None)
            self._triggers[trigger.id] = trigger
        return trigger

    def get(self, trigger_id: str) -> EventTrigger:
        t = self._triggers.get(trigger_id)
        if t is None:
            raise TriggersAndLinkOutputError("NOT_FOUND", f"触发器 {trigger_id} 不存在")
        return t

    def list(self, event_source: str | None = None, enabled_only: bool = False) -> list[EventTrigger]:
        items = list(self._triggers.values())
        if event_source:
            items = [t for t in items if t.event_source == event_source]
        if enabled_only:
            items = [t for t in items if t.enabled]
        return items

    def update(self, trigger_id: str, updates: dict[str, Any]) -> EventTrigger:
        t = self.get(trigger_id)
        if "event_source" in updates and updates["event_source"] not in _VALID_EVENT_SOURCES:
            raise TriggersAndLinkOutputError(
                "INVALID_EVENT_SOURCE", f"未知事件源：{updates['event_source']}",
            )
        for k, v in updates.items():
            if hasattr(t, k) and k != "id":
                setattr(t, k, v)
        return t

    def delete(self, trigger_id: str) -> bool:
        return self._triggers.pop(trigger_id, None) is not None

    # ---- fire ----
    def fire(
        self, trigger_id: str, event_payload: dict[str, Any] | None = None,
    ) -> TriggerFire:
        t = self.get(trigger_id)
        now = time.time()
        payload = event_payload or {}

        if not t.enabled:
            fire = TriggerFire(
                trigger_id=t.id, trigger_name=t.name,
                event_source=t.event_source,
                target_pipeline_id=t.target_pipeline_id,
                event_payload=payload, status="skipped", fired_at=now,
            )
            self._append_fire(fire)
            return fire

        if t.cooldown_seconds > 0 and t.last_fired_at > 0:
            if now - t.last_fired_at < t.cooldown_seconds:
                fire = TriggerFire(
                    trigger_id=t.id, trigger_name=t.name,
                    event_source=t.event_source,
                    target_pipeline_id=t.target_pipeline_id,
                    event_payload=payload, status="cooldown", fired_at=now,
                )
                self._append_fire(fire)
                return fire

        # fired
        t.last_fired_at = now
        t.fire_count += 1
        fire = TriggerFire(
            trigger_id=t.id, trigger_name=t.name,
            event_source=t.event_source,
            target_pipeline_id=t.target_pipeline_id,
            event_payload=payload, status="fired", fired_at=now,
        )
        self._append_fire(fire)
        return fire

    def list_fires(self, trigger_id: str | None = None, limit: int = 50) -> list[TriggerFire]:
        items = list(self._fires)
        if trigger_id:
            items = [f for f in items if f.trigger_id == trigger_id]
        # 最新在前
        items = list(reversed(items))
        if limit > 0:
            items = items[:limit]
        return items

    def _append_fire(self, fire: TriggerFire) -> None:
        with self._lock:
            if len(self._fires) >= _MAX_FIRES:
                self._fires.pop(0)  # FIFO 淘汰
            self._fires.append(fire)


# ════════════════════ #98 CompositeTriggerEngine ════════════════════

class CompositeTriggerEngine:
    def __init__(self) -> None:
        self._triggers: dict[str, CompositeTrigger] = {}
        self._fires: list[TriggerFire] = []
        self._lock = threading.Lock()

    # ---- CRUD ----
    def register(self, trigger: CompositeTrigger) -> CompositeTrigger:
        if not trigger.name:
            raise TriggersAndLinkOutputError("MISSING_NAME", "复合触发器名称不能为空")
        if trigger.logic not in _VALID_COMPOSITE_LOGICS:
            raise TriggersAndLinkOutputError(
                "INVALID_LOGIC", f"未知逻辑：{trigger.logic}",
            )
        if not trigger.child_trigger_ids:
            raise TriggersAndLinkOutputError("EMPTY_CHILDREN", "子触发器列表不能为空")
        if not trigger.target_pipeline_id:
            raise TriggersAndLinkOutputError(
                "MISSING_TARGET", "target_pipeline_id 不能为空",
            )
        with self._lock:
            if len(self._triggers) >= _MAX_COMPOSITES:
                oldest_id = next(iter(self._triggers))
                self._triggers.pop(oldest_id, None)
            self._triggers[trigger.id] = trigger
        return trigger

    def get(self, trigger_id: str) -> CompositeTrigger:
        t = self._triggers.get(trigger_id)
        if t is None:
            raise TriggersAndLinkOutputError("NOT_FOUND", f"复合触发器 {trigger_id} 不存在")
        return t

    def list(self, enabled_only: bool = False) -> list[CompositeTrigger]:
        items = list(self._triggers.values())
        if enabled_only:
            items = [t for t in items if t.enabled]
        return items

    def update(self, trigger_id: str, updates: dict[str, Any]) -> CompositeTrigger:
        t = self.get(trigger_id)
        if "logic" in updates and updates["logic"] not in _VALID_COMPOSITE_LOGICS:
            raise TriggersAndLinkOutputError(
                "INVALID_LOGIC", f"未知逻辑：{updates['logic']}",
            )
        for k, v in updates.items():
            if hasattr(t, k) and k != "id":
                setattr(t, k, v)
        return t

    def delete(self, trigger_id: str) -> bool:
        return self._triggers.pop(trigger_id, None) is not None

    # ---- evaluate + fire ----
    def evaluate(
        self, trigger_id: str, child_fires: dict[str, bool],
    ) -> dict[str, Any]:
        t = self.get(trigger_id)
        detail: dict[str, bool] = {}
        for cid in t.child_trigger_ids:
            detail[cid] = bool(child_fires.get(cid, False))
        if t.logic == "and":
            fired = all(detail.values())
        else:  # or
            fired = any(detail.values())
        return {
            "trigger_id": t.id,
            "logic": t.logic,
            "fired": fired,
            "detail": detail,
        }

    def fire(
        self, trigger_id: str, child_fires: dict[str, bool],
    ) -> TriggerFire:
        t = self.get(trigger_id)
        now = time.time()
        result = self.evaluate(trigger_id, child_fires)
        status = "fired" if result["fired"] else "skipped"
        if status == "fired":
            t.last_fired_at = now
            t.fire_count += 1
        fire = TriggerFire(
            trigger_id=t.id, trigger_name=t.name,
            event_source="composite",
            target_pipeline_id=t.target_pipeline_id,
            event_payload={"logic": t.logic, "detail": result["detail"]},
            status=status, fired_at=now,
        )
        with self._lock:
            if len(self._fires) >= _MAX_FIRES:
                self._fires.pop(0)
            self._fires.append(fire)
        return fire


# ════════════════════ #91 LinkTypeOutputEngine ════════════════════

class LinkTypeOutputEngine:
    def __init__(self) -> None:
        self._links: dict[str, LinkTypeDefinition] = {}
        self._lock = threading.Lock()

    def register(self, link: LinkTypeDefinition) -> LinkTypeDefinition:
        if not link.name:
            raise TriggersAndLinkOutputError("MISSING_NAME", "链接类型名称不能为空")
        if link.cardinality not in _VALID_CARDINALITIES:
            raise TriggersAndLinkOutputError(
                "INVALID_CARDINALITY", f"未知基数：{link.cardinality}",
            )
        if not link.source_object_type or not link.target_object_type:
            raise TriggersAndLinkOutputError(
                "MISSING_OBJECT_TYPE", "source/target_object_type 不能为空",
            )
        if not link.source_pk_field or not link.target_fk_field:
            raise TriggersAndLinkOutputError(
                "MISSING_KEY_FIELD", "source_pk_field/target_fk_field 不能为空",
            )
        with self._lock:
            # 重名检查
            for existing in self._links.values():
                if existing.name == link.name and existing.id != link.id:
                    raise TriggersAndLinkOutputError(
                        "NAME_DUPLICATE", f"链接类型名 '{link.name}' 已存在",
                    )
            if len(self._links) >= _MAX_LINKS:
                oldest_id = next(iter(self._links))
                self._links.pop(oldest_id, None)
            self._links[link.id] = link
        return link

    def get(self, link_id: str) -> LinkTypeDefinition:
        l = self._links.get(link_id)
        if l is None:
            raise TriggersAndLinkOutputError("NOT_FOUND", f"链接类型 {link_id} 不存在")
        return l

    def get_by_name(self, name: str) -> LinkTypeDefinition | None:
        for l in self._links.values():
            if l.name == name:
                return l
        return None

    def list(
        self,
        source_object_type: str | None = None,
        target_object_type: str | None = None,
    ) -> list[LinkTypeDefinition]:
        items = list(self._links.values())
        if source_object_type:
            items = [l for l in items if l.source_object_type == source_object_type]
        if target_object_type:
            items = [l for l in items if l.target_object_type == target_object_type]
        return items

    def update(self, link_id: str, updates: dict[str, Any]) -> LinkTypeDefinition:
        l = self.get(link_id)
        if "cardinality" in updates and updates["cardinality"] not in _VALID_CARDINALITIES:
            raise TriggersAndLinkOutputError(
                "INVALID_CARDINALITY", f"未知基数：{updates['cardinality']}",
            )
        if "name" in updates and updates["name"] != l.name:
            # 重名检查
            for existing in self._links.values():
                if existing.name == updates["name"] and existing.id != l.id:
                    raise TriggersAndLinkOutputError(
                        "NAME_DUPLICATE", f"链接类型名 '{updates['name']}' 已存在",
                    )
        for k, v in updates.items():
            if hasattr(l, k) and k != "id":
                setattr(l, k, v)
        return l

    def delete(self, link_id: str) -> bool:
        return self._links.pop(link_id, None) is not None

    def infer_from_objects(
        self,
        source_ot: str,
        target_ot: str,
        rows: list[dict[str, Any]],
        fk_field: str,
        display_field: str = "",
    ) -> LinkTypeDefinition:
        """从对象数据推断链接类型（默认 many_to_one）。"""
        if not rows:
            raise TriggersAndLinkOutputError(
                "EMPTY_ROWS", "rows 不能为空",
            )
        # 默认 many_to_one：多个 source 指向同一 target
        link = LinkTypeDefinition(
            name=f"{source_ot}_to_{target_ot}",
            display_name=f"{source_ot} → {target_ot}",
            cardinality="many_to_one",
            source_object_type=source_ot,
            target_object_type=target_ot,
            source_pk_field="id",
            target_fk_field=fk_field,
            display_field=display_field,
        )
        return self.register(link)

    def preview_links(
        self, link_id: str, rows: list[dict[str, Any]], limit: int = 100,
    ) -> list[dict[str, Any]]:
        """预览链接实例。"""
        l = self.get(link_id)
        results: list[dict[str, Any]] = []
        for row in rows[:limit]:
            source_pk = row.get(l.source_pk_field)
            target_fk = row.get(l.target_fk_field)
            if source_pk is None or target_fk is None:
                continue
            display_val = row.get(l.display_field) if l.display_field else ""
            results.append({
                "link_type_id": l.id,
                "link_type_name": l.name,
                "source_object_id": str(source_pk),
                "source_object_type": l.source_object_type,
                "target_object_id": str(target_fk),
                "target_object_type": l.target_object_type,
                "display": str(display_val) if display_val else str(source_pk),
                "cardinality": l.cardinality,
            })
        return results


# ════════════════════ 单例 ════════════════════

_event_trigger_engine: EventTriggerEngine | None = None
_composite_trigger_engine: CompositeTriggerEngine | None = None
_link_type_output_engine: LinkTypeOutputEngine | None = None
_singleton_lock = threading.Lock()


def get_event_trigger_engine() -> EventTriggerEngine:
    global _event_trigger_engine
    if _event_trigger_engine is None:
        with _singleton_lock:
            if _event_trigger_engine is None:
                _event_trigger_engine = EventTriggerEngine()
    return _event_trigger_engine


def get_composite_trigger_engine() -> CompositeTriggerEngine:
    global _composite_trigger_engine
    if _composite_trigger_engine is None:
        with _singleton_lock:
            if _composite_trigger_engine is None:
                _composite_trigger_engine = CompositeTriggerEngine()
    return _composite_trigger_engine


def get_link_type_output_engine() -> LinkTypeOutputEngine:
    global _link_type_output_engine
    if _link_type_output_engine is None:
        with _singleton_lock:
            if _link_type_output_engine is None:
                _link_type_output_engine = LinkTypeOutputEngine()
    return _link_type_output_engine
