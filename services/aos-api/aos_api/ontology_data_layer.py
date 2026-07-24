"""W2-L · Object 数据层增强：Shared Property + Type Coherence + L1 Join + Computed Property."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ─────────────── #33 Shared Property ───────────────

class SharedProperty(BaseModel):
    id: str = Field(default_factory=lambda: _uid("sp"))
    name: str
    data_type: str = "string"
    description: str = ""
    backing_column: str = ""
    nullable: bool = True
    referenced_by: list[str] = Field(default_factory=list)  # OT IDs
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class SharedPropertyError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class SharedPropertyEngine:
    """跨 Object Type 共享属性引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._props: dict[str, SharedProperty] = {}

    def create(self, prop: SharedProperty) -> SharedProperty:
        with self._lock:
            self._props[prop.id] = prop
        return prop

    def get(self, prop_id: str) -> SharedProperty:
        prop = self._props.get(prop_id)
        if not prop:
            raise SharedPropertyError("NOT_FOUND", f"共享属性 {prop_id} 不存在")
        return prop

    def list(self) -> list[SharedProperty]:
        with self._lock:
            return list(self._props.values())

    def update(self, prop_id: str, updates: dict[str, Any]) -> SharedProperty:
        with self._lock:
            prop = self._props.get(prop_id)
            if not prop:
                raise SharedPropertyError("NOT_FOUND", f"共享属性 {prop_id} 不存在")
            for k, v in updates.items():
                if k not in ("id", "created_at"):
                    setattr(prop, k, v)
            prop.updated_at = _now()
            return prop

    def delete(self, prop_id: str) -> bool:
        with self._lock:
            prop = self._props.get(prop_id)
            if not prop:
                raise SharedPropertyError("NOT_FOUND", f"共享属性 {prop_id} 不存在")
            if prop.referenced_by:
                raise SharedPropertyError(
                    "STILL_REFERENCED",
                    f"共享属性 {prop_id} 被 {len(prop.referenced_by)} 个 OT 引用，无法删除",
                )
            del self._props[prop_id]
            return True

    def attach(self, prop_id: str, object_type: str) -> SharedProperty:
        with self._lock:
            prop = self._props.get(prop_id)
            if not prop:
                raise SharedPropertyError("NOT_FOUND", f"共享属性 {prop_id} 不存在")
            if object_type not in prop.referenced_by:
                prop.referenced_by.append(object_type)
            prop.updated_at = _now()
            return prop

    def detach(self, prop_id: str, object_type: str) -> SharedProperty:
        with self._lock:
            prop = self._props.get(prop_id)
            if not prop:
                raise SharedPropertyError("NOT_FOUND", f"共享属性 {prop_id} 不存在")
            if object_type in prop.referenced_by:
                prop.referenced_by.remove(object_type)
            prop.updated_at = _now()
            return prop

    def reset(self) -> None:
        with self._lock:
            self._props.clear()


# ─────────────── #29 Type Coherence ───────────────

class CoherenceConflict(BaseModel):
    code: str           # TC-01 ~ TC-04
    severity: str       # error / warning
    object_type: str
    property_name: str
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class TypeCoherenceEngine:
    """类型严格一致性检测引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # 注册的 schema 快照: object_type -> {properties: [{name, data_type, backing_column, nullable}], dataset_columns: [{name, data_type, nullable}]}
        self._schemas: dict[str, dict[str, Any]] = {}

    def register_schema(
        self,
        object_type: str,
        *,
        properties: list[dict[str, Any]],
        dataset_columns: list[dict[str, Any]],
    ) -> None:
        with self._lock:
            self._schemas[object_type] = {
                "properties": properties,
                "dataset_columns": dataset_columns,
            }

    def check(self, object_type: str) -> list[CoherenceConflict]:
        """检查指定 OT 的 Schema 一致性。"""
        with self._lock:
            schema = self._schemas.get(object_type)
        if not schema:
            return []

        conflicts: list[CoherenceConflict] = []
        ot_props = schema["properties"]
        ds_cols = schema["dataset_columns"]
        ds_col_map: dict[str, dict[str, Any]] = {c["name"]: c for c in ds_cols}

        for prop in ot_props:
            pname = prop.get("name", "")
            ptype = prop.get("data_type", "string")
            pcol = prop.get("backing_column", "")
            pnullable = prop.get("nullable", True)

            if not pcol:
                continue

            # TC-02: 缺失列
            if pcol not in ds_col_map:
                conflicts.append(CoherenceConflict(
                    code="TC-02",
                    severity="error",
                    object_type=object_type,
                    property_name=pname,
                    message=f"OT 属性 {pname} 引用的 backing_column '{pcol}' 在 dataset 中不存在",
                    detail={"backing_column": pcol, "available": list(ds_col_map.keys())},
                ))
                continue

            ds_col = ds_col_map[pcol]

            # TC-01: 类型不匹配
            ds_type = ds_col.get("data_type", "string")
            if not self._types_compatible(ptype, ds_type):
                conflicts.append(CoherenceConflict(
                    code="TC-01",
                    severity="error",
                    object_type=object_type,
                    property_name=pname,
                    message=f"OT 属性 {pname} 类型 '{ptype}' 与 dataset 列 '{pcol}' 类型 '{ds_type}' 不匹配",
                    detail={"ot_type": ptype, "ds_type": ds_type},
                ))

            # TC-04: 可空性冲突
            ds_nullable = ds_col.get("nullable", True)
            if not pnullable and ds_nullable:
                conflicts.append(CoherenceConflict(
                    code="TC-04",
                    severity="warning",
                    object_type=object_type,
                    property_name=pname,
                    message=f"OT 属性 {pname} 声明 nullable=false 但 dataset 列 '{pcol}' 允许 null",
                    detail={"ot_nullable": False, "ds_nullable": True},
                ))

        # TC-03: 多余列
        ot_col_names = {p.get("backing_column", "") for p in ot_props if p.get("backing_column")}
        for ds_col in ds_cols:
            cn = ds_col["name"]
            if cn not in ot_col_names:
                conflicts.append(CoherenceConflict(
                    code="TC-03",
                    severity="warning",
                    object_type=object_type,
                    property_name="—",
                    message=f"dataset 列 '{cn}' 未被 OT 声明",
                    detail={"column": cn},
                ))

        return conflicts

    def check_all(self) -> list[CoherenceConflict]:
        """检查所有已注册的 OT。"""
        all_conflicts: list[CoherenceConflict] = []
        for ot in list(self._schemas.keys()):
            all_conflicts.extend(self.check(ot))
        return all_conflicts

    def _types_compatible(self, ot_type: str, ds_type: str) -> bool:
        """简单类型兼容性检查。"""
        # 规范化
        ot = ot_type.lower().strip()
        ds = ds_type.lower().strip()
        if ot == ds:
            return True
        # 兼容组
        compat_groups = [
            {"string", "text", "varchar", "char"},
            {"int", "integer", "long", "bigint", "int64"},
            {"float", "double", "decimal", "numeric", "float64"},
            {"bool", "boolean"},
            {"timestamp", "datetime", "date"},
        ]
        for group in compat_groups:
            if ot in group and ds in group:
                return True
        return False

    def reset(self) -> None:
        with self._lock:
            self._schemas.clear()


# ─────────────── #30 L1 Join + Computed Property ───────────────

class JoinSpec(BaseModel):
    dataset: str
    join_type: str = "left"  # left / inner / outer
    left_key: str
    right_key: str
    columns: list[str] = Field(default_factory=list)  # 空=全部


class L1JoinConfig(BaseModel):
    id: str = Field(default_factory=lambda: _uid("l1j"))
    object_type: str
    primary_dataset: str
    primary_key: str
    joins: list[JoinSpec] = Field(default_factory=list)
    created_at: str = Field(default_factory=_now)
    updated_at: str = Field(default_factory=_now)


class ComputedProperty(BaseModel):
    id: str = Field(default_factory=lambda: _uid("cp"))
    object_type: str
    property_name: str
    function_name: str
    input_mapping: dict[str, str] = Field(default_factory=dict)
    output_type: str = "string"
    created_at: str = Field(default_factory=_now)


class L1JoinError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class L1JoinEngine:
    """解法 A: L1 Join 宽表 + 解法 C: Computed Property 引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._joins: dict[str, L1JoinConfig] = {}
        self._computed: dict[str, ComputedProperty] = {}

    # ── L1 Join ──
    def create_join(self, config: L1JoinConfig) -> L1JoinConfig:
        with self._lock:
            self._joins[config.id] = config
        return config

    def get_join(self, join_id: str) -> L1JoinConfig:
        j = self._joins.get(join_id)
        if not j:
            raise L1JoinError("NOT_FOUND", f"L1 Join 配置 {join_id} 不存在")
        return j

    def list_joins(self, *, object_type: str | None = None) -> list[L1JoinConfig]:
        with self._lock:
            joins = list(self._joins.values())
        if object_type:
            joins = [j for j in joins if j.object_type == object_type]
        return joins

    def preview_join(self, join_id: str) -> dict[str, Any]:
        """预览 join 后的结果列。"""
        config = self.get_join(join_id)
        columns: list[dict[str, str]] = []

        # 主表列
        columns.append({"name": config.primary_key, "source": config.primary_dataset, "type": "key"})
        # 模拟主表的几列
        columns.extend([
            {"name": f"{config.primary_dataset}.col_{i}", "source": config.primary_dataset, "type": "data"}
            for i in range(1, 4)
        ])

        # join 表列
        for join in config.joins:
            if join.columns:
                for col in join.columns:
                    columns.append({"name": f"{join.dataset}.{col}", "source": join.dataset, "type": "data"})
            else:
                columns.append({"name": f"{join.dataset}.{join.right_key}", "source": join.dataset, "type": "key"})
                columns.extend([
                    {"name": f"{join.dataset}.col_{i}", "source": join.dataset, "type": "data"}
                    for i in range(1, 3)
                ])

        return {
            "joinId": join_id,
            "objectType": config.object_type,
            "totalColumns": len(columns),
            "columns": columns,
        }

    def delete_join(self, join_id: str) -> bool:
        with self._lock:
            if join_id not in self._joins:
                raise L1JoinError("NOT_FOUND", f"L1 Join 配置 {join_id} 不存在")
            del self._joins[join_id]
            return True

    # ── Computed Property ──
    def create_computed(self, prop: ComputedProperty) -> ComputedProperty:
        with self._lock:
            self._computed[prop.id] = prop
        return prop

    def get_computed(self, prop_id: str) -> ComputedProperty:
        p = self._computed.get(prop_id)
        if not p:
            raise L1JoinError("NOT_FOUND", f"计算属性 {prop_id} 不存在")
        return p

    def list_computed(self, *, object_type: str | None = None) -> list[ComputedProperty]:
        with self._lock:
            props = list(self._computed.values())
        if object_type:
            props = [p for p in props if p.object_type == object_type]
        return props

    def delete_computed(self, prop_id: str) -> bool:
        with self._lock:
            if prop_id not in self._computed:
                raise L1JoinError("NOT_FOUND", f"计算属性 {prop_id} 不存在")
            del self._computed[prop_id]
            return True

    def reset(self) -> None:
        with self._lock:
            self._joins.clear()
            self._computed.clear()


# ─────────────── 单例 ───────────────

_sp_engine: SharedPropertyEngine | None = None
_tc_engine: TypeCoherenceEngine | None = None
_l1_engine: L1JoinEngine | None = None
_lock = threading.Lock()


def get_sp_engine() -> SharedPropertyEngine:
    global _sp_engine
    if _sp_engine is None:
        with _lock:
            if _sp_engine is None:
                _sp_engine = SharedPropertyEngine()
    return _sp_engine


def get_tc_engine() -> TypeCoherenceEngine:
    global _tc_engine
    if _tc_engine is None:
        with _lock:
            if _tc_engine is None:
                _tc_engine = TypeCoherenceEngine()
    return _tc_engine


def get_l1_engine() -> L1JoinEngine:
    global _l1_engine
    if _l1_engine is None:
        with _lock:
            if _l1_engine is None:
                _l1_engine = L1JoinEngine()
    return _l1_engine
