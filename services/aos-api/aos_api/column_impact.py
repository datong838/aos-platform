"""W2-AG · 列级影响分析（#109 增量补丁）.

- ColumnImpactEngine：列级影响分析（基于规则图做下游传播，BFS + visited 防环路）

不修改 W2-E #4 的 lineage_views.py，纯新增引擎。

详见 docs/palantier/20_tech/220tech_w2-ag-column-impact.md。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

# ════════════════════ 常量 ════════════════════

_MAX_RULES = 200

# ════════════════════ 数据模型 ════════════════════

class ColumnImpactRule(BaseModel):
    """列级影响规则（来源 → 下游列表）。"""
    id: str = Field(default_factory=lambda: "cir-" + uuid.uuid4().hex[:10])
    source_dataset_rid: str
    source_column: str
    downstream_datasets: list[str] = Field(default_factory=list)
    downstream_columns: list[str] = Field(default_factory=list)
    transform_expr: str = ""
    created_at: float = Field(default_factory=lambda: time.time())


class ImpactResult(BaseModel):
    """影响分析结果。"""
    source_dataset_rid: str
    source_column: str
    impacted_datasets: list[str] = Field(default_factory=list)
    impacted_columns: list[str] = Field(default_factory=list)
    depth: int = 0
    analyzed_at: float = Field(default_factory=lambda: time.time())


# ════════════════════ 错误 ════════════════════

class ColumnImpactError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════ ColumnImpactEngine ════════════════════

class ColumnImpactEngine:
    def __init__(self) -> None:
        self._rules: dict[str, ColumnImpactRule] = {}
        self._lock = threading.Lock()

    def register(self, rule: ColumnImpactRule) -> ColumnImpactRule:
        if not rule.source_dataset_rid:
            raise ColumnImpactError("MISSING_SOURCE_DATASET", "source_dataset_rid 不能为空")
        if not rule.source_column:
            raise ColumnImpactError("MISSING_SOURCE_COLUMN", "source_column 不能为空")
        with self._lock:
            if len(self._rules) >= _MAX_RULES:
                oldest_id = next(iter(self._rules))
                self._rules.pop(oldest_id, None)
            self._rules[rule.id] = rule
        return rule

    def get(self, rule_id: str) -> ColumnImpactRule:
        r = self._rules.get(rule_id)
        if r is None:
            raise ColumnImpactError("NOT_FOUND", f"规则 {rule_id} 不存在")
        return r

    def list(self, source_dataset_rid: str | None = None) -> list[ColumnImpactRule]:
        items = list(self._rules.values())
        if source_dataset_rid:
            items = [r for r in items if r.source_dataset_rid == source_dataset_rid]
        return items

    def delete(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    def analyze_impact(
        self, source_dataset_rid: str, source_column: str,
    ) -> ImpactResult:
        """BFS 查找所有下游影响，visited 防环路。"""
        if not source_dataset_rid:
            raise ColumnImpactError("MISSING_SOURCE_DATASET", "source_dataset_rid 不能为空")
        if not source_column:
            raise ColumnImpactError("MISSING_SOURCE_COLUMN", "source_column 不能为空")

        impacted_datasets: set[str] = set()
        impacted_columns: set[str] = set()
        visited: set[tuple[str, str]] = set()
        depth = 0

        # BFS 队列：(dataset, column)
        queue: list[tuple[str, str]] = [(source_dataset_rid, source_column)]
        visited.add((source_dataset_rid, source_column))

        while queue:
            next_queue: list[tuple[str, str]] = []
            for cur_ds, cur_col in queue:
                # 查找所有以 (cur_ds, cur_col) 为源的规则
                matching = [
                    r for r in self._rules.values()
                    if r.source_dataset_rid == cur_ds and r.source_column == cur_col
                ]
                for rule in matching:
                    for ds in rule.downstream_datasets:
                        if ds not in impacted_datasets:
                            impacted_datasets.add(ds)
                    for col in rule.downstream_columns:
                        if col not in impacted_columns:
                            impacted_columns.add(col)
                        # 解析 "ds.col" 形式，作为下一层 BFS 入口
                        if "." in col:
                            parts = col.split(".", 1)
                            next_ds, next_col = parts[0], parts[1]
                            if (next_ds, next_col) not in visited:
                                visited.add((next_ds, next_col))
                                next_queue.append((next_ds, next_col))
            if next_queue:
                depth += 1
            queue = next_queue

        return ImpactResult(
            source_dataset_rid=source_dataset_rid,
            source_column=source_column,
            impacted_datasets=sorted(impacted_datasets),
            impacted_columns=sorted(impacted_columns),
            depth=depth,
        )


# ════════════════════ 单例 ════════════════════

_impact_engine: ColumnImpactEngine | None = None
_singleton_lock = threading.Lock()


def get_impact_engine() -> ColumnImpactEngine:
    global _impact_engine
    if _impact_engine is None:
        with _singleton_lock:
            if _impact_engine is None:
                _impact_engine = ColumnImpactEngine()
    return _impact_engine
