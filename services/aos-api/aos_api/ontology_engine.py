"""Phase 4 · Ontology 数字孪生引擎.

对象类型、对象实例、属性、列映射、automap、preview、recent、count、branches、graph-health。
模式：Singleton + Pydantic + threading.Lock。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

_LOCK = threading.Lock()


# ───────────────────────── Pydantic Models ─────────────────────────


class Property(BaseModel):
    id: str = Field(default_factory=lambda: "prop-" + uuid.uuid4().hex[:6])
    name: str
    display_name: str = ""
    datatype: str = "string"  # string|int|double|boolean|date|datetime|geo|json
    nullable: bool = True
    is_primary_key: bool = False
    is_display_name: bool = False
    description: str = ""
    created_at: float = Field(default_factory=lambda: time.time())


class ObjectType(BaseModel):
    id: str = Field(default_factory=lambda: "ot-" + uuid.uuid4().hex[:8])
    name: str  # customer, order, product...
    display_name: str = ""
    plural_name: str = ""
    icon: str = ""
    description: str = ""
    backing_dataset: str = ""
    properties: list[Property] = Field(default_factory=list)
    status: str = "active"  # active|draft|archived
    category: str = "business"  # business|technical|reference
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class ObjectInstance(BaseModel):
    id: str = Field(default_factory=lambda: "obj-" + uuid.uuid4().hex[:8])
    object_type_id: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


class ColumnMapping(BaseModel):
    id: str = Field(default_factory=lambda: "cm-" + uuid.uuid4().hex[:6])
    object_type_id: str
    source_column: str
    target_property: str
    confidence: float = 1.0
    auto: bool = False
    status: str = "mapped"  # mapped|skipped|error


class OntologyBranch(BaseModel):
    id: str = Field(default_factory=lambda: "ob-" + uuid.uuid4().hex[:8])
    name: str
    parent_branch: str = "main"
    status: str = "active"  # active|merged|abandoned
    description: str = ""
    created_by: str = "system"
    created_at: float = Field(default_factory=lambda: time.time())
    updated_at: float = Field(default_factory=lambda: time.time())


# ───────────────────────── Engine ─────────────────────────


class OntologyEngine:
    """Ontology 数字孪生核心引擎."""

    _instance: "OntologyEngine | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "OntologyEngine":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._object_types: dict[str, ObjectType] = {}
                    inst._objects: dict[str, ObjectInstance] = {}
                    inst._column_mappings: dict[str, list[ColumnMapping]] = {}
                    inst._branches: dict[str, OntologyBranch] = {}
                    inst._recent: list[dict[str, Any]] = []
                    inst._count: int = 0
                    cls._instance = inst
        return cls._instance

    # ── ObjectTypes ──
    def create_object_type(self, name: str, **kwargs: Any) -> ObjectType:
        with _LOCK:
            ot = ObjectType(name=name, **kwargs)
            self._object_types[ot.id] = ot
            return ot

    def get_object_type(self, ot_id: str) -> ObjectType | None:
        return self._object_types.get(ot_id)

    def list_object_types(
        self,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> tuple[list[ObjectType], int]:
        items = list(self._object_types.values())
        if search:
            s = search.lower()
            items = [o for o in items if s in o.name.lower() or s in o.display_name.lower() or s in o.description.lower()]
        reverse = sort_order == "desc"
        try:
            items.sort(key=lambda o: getattr(o, sort_by, 0), reverse=reverse)
        except Exception:
            items.sort(key=lambda o: o.updated_at, reverse=reverse)
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def update_object_type(self, ot_id: str, **kwargs: Any) -> ObjectType:
        with _LOCK:
            ot = self._object_types.get(ot_id)
            if ot is None:
                raise KeyError(f"ObjectType {ot_id} not found")
            for k, v in kwargs.items():
                if hasattr(ot, k) and k != "id":
                    setattr(ot, k, v)
            ot.updated_at = time.time()
            return ot

    def delete_object_type(self, ot_id: str) -> bool:
        with _LOCK:
            return self._object_types.pop(ot_id, None) is not None

    def count_instances(self, ot_id: str) -> int:
        return sum(1 for o in self._objects.values() if o.object_type_id == ot_id)

    # ── Objects ──
    def create_object(self, object_type_id: str, name: str, **kwargs: Any) -> ObjectInstance:
        with _LOCK:
            obj = ObjectInstance(object_type_id=object_type_id, name=name, **kwargs)
            self._objects[obj.id] = obj
            return obj

    def get_object(self, obj_id: str) -> ObjectInstance | None:
        return self._objects.get(obj_id)

    def list_objects(
        self,
        object_type_id: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ObjectInstance], int]:
        items = list(self._objects.values())
        if object_type_id:
            items = [o for o in items if o.object_type_id == object_type_id]
        if search:
            s = search.lower()
            items = [o for o in items if s in o.name.lower()]
        total = len(items)
        start = (page - 1) * page_size
        return items[start : start + page_size], total

    def update_object(self, obj_id: str, **kwargs: Any) -> ObjectInstance:
        with _LOCK:
            obj = self._objects.get(obj_id)
            if obj is None:
                raise KeyError(f"Object {obj_id} not found")
            for k, v in kwargs.items():
                if hasattr(obj, k) and k != "id":
                    setattr(obj, k, v)
            obj.updated_at = time.time()
            return obj

    def delete_object(self, obj_id: str) -> bool:
        with _LOCK:
            return self._objects.pop(obj_id, None) is not None

    # ── Properties ──
    def list_properties(self, ot_id: str) -> list[Property]:
        ot = self._object_types.get(ot_id)
        return list(ot.properties) if ot else []

    def add_property(self, ot_id: str, name: str, **kwargs: Any) -> Property:
        with _LOCK:
            ot = self._object_types.get(ot_id)
            if ot is None:
                raise KeyError(f"ObjectType {ot_id} not found")
            prop = Property(name=name, **kwargs)
            ot.properties.append(prop)
            ot.updated_at = time.time()
            return prop

    def update_property(self, ot_id: str, prop_id: str, **kwargs: Any) -> Property:
        with _LOCK:
            ot = self._object_types.get(ot_id)
            if ot is None:
                raise KeyError(f"ObjectType {ot_id} not found")
            prop = next((item for item in ot.properties if item.id == prop_id), None)
            if prop is None:
                raise KeyError(f"Property {prop_id} not found")
            for key, value in kwargs.items():
                if key != "name" and hasattr(prop, key):
                    setattr(prop, key, value)
            ot.updated_at = time.time()
            return prop

    def delete_property(self, ot_id: str, prop_id: str) -> bool:
        with _LOCK:
            ot = self._object_types.get(ot_id)
            if ot is None:
                return False
            before = len(ot.properties)
            ot.properties = [p for p in ot.properties if p.id != prop_id]
            deleted = len(ot.properties) < before
            if deleted:
                prop_names = {p.name for p in ot.properties}
                self._column_mappings[ot_id] = [
                    mapping for mapping in self._column_mappings.get(ot_id, [])
                    if mapping.target_property in prop_names
                ]
                ot.updated_at = time.time()
            return deleted

    # ── Column Mapping ──
    def list_column_mapping(self, ot_id: str) -> list[ColumnMapping]:
        return list(self._column_mappings.get(ot_id, []))

    def set_column_mapping(self, ot_id: str, mappings: list[dict[str, Any]]) -> list[ColumnMapping]:
        with _LOCK:
            result = [ColumnMapping(object_type_id=ot_id, **m) for m in mappings]
            self._column_mappings[ot_id] = result
            return result

    def automap(self, ot_id: str, columns: list[str] | None = None) -> list[ColumnMapping]:
        """Auto-infer column→property mapping based on name similarity."""
        with _LOCK:
            ot = self._object_types.get(ot_id)
            if ot is None:
                raise KeyError(f"ObjectType {ot_id} not found")
            props = ot.properties
            cols = columns or [c for c in self._infer_columns(ot_id)]
            result: list[ColumnMapping] = []
            for col in cols:
                best = self._match(col, props)
                if best:
                    result.append(
                        ColumnMapping(
                            object_type_id=ot_id,
                            source_column=col,
                            target_property=best.name,
                            confidence=0.92,
                            auto=True,
                        )
                    )
                else:
                    result.append(
                        ColumnMapping(
                            object_type_id=ot_id,
                            source_column=col,
                            target_property="",
                            confidence=0.0,
                            auto=True,
                            status="skipped",
                        )
                    )
            self._column_mappings[ot_id] = result
            return result

    def _infer_columns(self, ot_id: str) -> list[str]:
        # 模拟数据源列名：取属性 name 的 snake_case 化 + 一些常见列
        ot = self._object_types.get(ot_id)
        if not ot:
            return []
        cols = [p.name for p in ot.properties]
        cols.extend(["record_id", "created_at", "updated_at"])
        return cols

    @staticmethod
    def _match(col: str, props: list[Property]) -> Property | None:
        cl = col.lower().replace("-", "_").replace(" ", "_")
        for p in props:
            if p.name.lower() == cl:
                return p
        for p in props:
            if cl in p.name.lower() or p.name.lower() in cl:
                return p
        return None

    # ── Preview ──
    def preview(self, ot_id: str, limit: int = 20) -> dict[str, Any]:
        ot = self._object_types.get(ot_id)
        if ot is None:
            raise KeyError(f"ObjectType {ot_id} not found")
        objs = [o for o in self._objects.values() if o.object_type_id == ot_id][:limit]
        columns = [p.name for p in ot.properties]
        rows = []
        for o in objs:
            row = {col: o.properties.get(col, "") for col in columns}
            rows.append(row)
        return {
            "object_type_id": ot_id,
            "columns": columns,
            "rows": rows,
            "total": self.count_instances(ot_id),
        }

    # ── Recent ──
    def list_recent(self, user_id: str = "default", limit: int = 10) -> list[dict[str, Any]]:
        items = [r for r in self._recent if r.get("user_id", "default") == user_id]
        return items[-limit:][::-1]

    def add_recent(self, object_type_id: str, user_id: str = "default") -> None:
        with _LOCK:
            self._recent.append(
                {
                    "object_type_id": object_type_id,
                    "user_id": user_id,
                    "viewed_at": time.time(),
                }
            )
            # 仅保留最近 100 条
            if len(self._recent) > 100:
                self._recent = self._recent[-100:]

    # ── Branches ──
    def create_branch(self, name: str, **kwargs: Any) -> OntologyBranch:
        with _LOCK:
            br = OntologyBranch(name=name, **kwargs)
            self._branches[br.id] = br
            return br

    def get_branch(self, br_id: str) -> OntologyBranch | None:
        return self._branches.get(br_id)

    def list_branches(self, status: str | None = None) -> list[OntologyBranch]:
        items = list(self._branches.values())
        if status:
            items = [b for b in items if b.status == status]
        return items

    def update_branch(self, br_id: str, **kwargs: Any) -> OntologyBranch:
        with _LOCK:
            br = self._branches.get(br_id)
            if br is None:
                raise KeyError(f"Branch {br_id} not found")
            for k, v in kwargs.items():
                if hasattr(br, k) and k != "id":
                    setattr(br, k, v)
            br.updated_at = time.time()
            return br

    def delete_branch(self, br_id: str) -> bool:
        with _LOCK:
            return self._branches.pop(br_id, None) is not None

    # ── Graph Health ──
    def graph_health(self) -> dict[str, Any]:
        total_types = len(self._object_types)
        total_objects = len(self._objects)
        total_props = sum(len(o.properties) for o in self._object_types.values())
        # 孤立节点：未出现在任何 column mapping 的对象类型
        mapped_ots = set(self._column_mappings.keys())
        orphan_types = [o.id for o in self._object_types.values() if o.id not in mapped_ots]
        coverage = (total_types - len(orphan_types)) / total_types if total_types else 0.0
        return {
            "total_object_types": total_types,
            "total_objects": total_objects,
            "total_properties": total_props,
            "orphan_types": orphan_types,
            "orphan_count": len(orphan_types),
            "mapping_coverage": round(coverage, 4),
            "healthy": len(orphan_types) == 0,
            "checked_at": time.time(),
        }

    # ── Util ──
    def reset(self) -> None:
        with _LOCK:
            self._object_types.clear()
            self._objects.clear()
            self._column_mappings.clear()
            self._branches.clear()
            self._recent.clear()


def get_engine() -> OntologyEngine:
    return OntologyEngine()
