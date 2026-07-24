"""W2-#15 · Expectation 数据期望引擎。

支持两种检查类型：
  - pk_unique:  主键唯一性检查
  - row_count:  行数范围检查（min/max）

在 Pipeline/Funnel 执行时可选触发，severity=error 未通过应中止管道。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ExpectationType(str, Enum):
    PK_UNIQUE = "pk_unique"
    ROW_COUNT = "row_count"


class ExpectationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class Expectation(BaseModel):
    id: str = Field(default_factory=lambda: "exp-" + uuid.uuid4().hex[:10])
    name: str
    type: ExpectationType
    config: dict[str, Any] = Field(default_factory=dict)
    severity: Literal["error", "warn"] = "error"
    enabled: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExpectationResult(BaseModel):
    expectation_id: str
    expectation_name: str
    type: ExpectationType
    passed: bool
    severity: str
    message: str
    violations: list[dict[str, Any]] = Field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ExpectationEngine:
    """Expectation 检查引擎（内存存储）。"""

    def __init__(self) -> None:
        self._store: dict[str, Expectation] = {}

    # ── CRUD ──

    def create(self, expectation: Expectation) -> Expectation:
        self._store[expectation.id] = expectation
        return expectation

    def get(self, eid: str) -> Expectation | None:
        return self._store.get(eid)

    def list_all(self) -> list[Expectation]:
        return list(self._store.values())

    def delete(self, eid: str) -> bool:
        return self._store.pop(eid, None) is not None

    # ── 检查 ──

    def check(self, expectation: Expectation, rows: list[dict[str, Any]]) -> ExpectationResult:
        if not expectation.enabled:
            return ExpectationResult(
                expectation_id=expectation.id,
                expectation_name=expectation.name,
                type=expectation.type,
                passed=True,
                severity=expectation.severity,
                message="期望已禁用，跳过检查",
            )

        if expectation.type == ExpectationType.PK_UNIQUE:
            return self._check_pk_unique(expectation, rows)
        if expectation.type == ExpectationType.ROW_COUNT:
            return self._check_row_count(expectation, rows)

        raise ExpectationError("UNKNOWN_TYPE", f"未知期望类型：{expectation.type}")

    def check_all(
        self, expectations: list[Expectation], rows: list[dict[str, Any]]
    ) -> list[ExpectationResult]:
        return [self.check(e, rows) for e in expectations if e.enabled]

    def has_blocking_failure(self, results: list[ExpectationResult]) -> bool:
        """是否有 error 级别未通过的检查。"""
        return any(not r.passed and r.severity == "error" for r in results)

    # ── 内部实现 ──

    def _check_pk_unique(
        self, expectation: Expectation, rows: list[dict[str, Any]]
    ) -> ExpectationResult:
        pk_field = str(expectation.config.get("primary_key", "id"))
        seen: dict[Any, int] = {}
        for r in rows:
            val = r.get(pk_field)
            if val is None:
                continue
            seen[val] = seen.get(val, 0) + 1

        duplicates = {k: v for k, v in seen.items() if v > 1}
        passed = len(duplicates) == 0
        violations = [{"primary_key": k, "count": v} for k, v in duplicates.items()]

        if passed:
            msg = f"主键 '{pk_field}' 唯一性检查通过（{len(seen)} 个唯一值）"
        else:
            msg = f"主键 '{pk_field}' 存在 {len(duplicates)} 个重复值"

        return ExpectationResult(
            expectation_id=expectation.id,
            expectation_name=expectation.name,
            type=ExpectationType.PK_UNIQUE,
            passed=passed,
            severity=expectation.severity,
            message=msg,
            violations=violations,
        )

    def _check_row_count(
        self, expectation: Expectation, rows: list[dict[str, Any]]
    ) -> ExpectationResult:
        count = len(rows)
        min_val = expectation.config.get("min", 0)
        max_val = expectation.config.get("max")
        violations: list[dict[str, Any]] = []

        if count < min_val:
            violations.append({"actual": count, "min": min_val, "reason": "低于最小行数"})
        if max_val is not None and count > max_val:
            violations.append({"actual": count, "max": max_val, "reason": "超过最大行数"})

        passed = len(violations) == 0
        if passed:
            range_desc = f"[{min_val}, {max_val if max_val is not None else '∞'}]"
            msg = f"行数 {count} 在范围 {range_desc} 内"
        else:
            msg = f"行数 {count} 不在期望范围内"

        return ExpectationResult(
            expectation_id=expectation.id,
            expectation_name=expectation.name,
            type=ExpectationType.ROW_COUNT,
            passed=passed,
            severity=expectation.severity,
            message=msg,
            violations=violations,
        )


# ── 单例 ──

_engine = ExpectationEngine()


def get_engine() -> ExpectationEngine:
    return _engine
