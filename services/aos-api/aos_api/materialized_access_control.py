"""W2-BG 批次引擎 — 对象物化 + 行级权限 + 列级权限 + Agent六工具."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

_MAX_ENTRIES = 200


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime())


class MaterializationEngineError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class RowLevelEngineError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class ColumnLevelEngineError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class AgentToolsEngineError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


MaterializationType = Literal["auto", "manual", "scheduled"]
MaterializationStatus = Literal["pending", "running", "completed", "failed"]

RowLevelPolicyType = Literal["filter", "mask", "join"]
RowLevelStatus = Literal["active", "inactive", "draft"]

ColumnLevelPolicyType = Literal["include", "exclude", "mask", "encrypt"]
ColumnLevelStatus = Literal["active", "inactive", "draft"]

ToolType = Literal["Action", "Query", "Function", "Var", "Command", "Clarify"]
ToolStatus = Literal["enabled", "disabled"]


class MaterializationTask(BaseModel):
    task_id: str = Field(default_factory=lambda: f"mt-{uuid.uuid4().hex[:8]}")
    object_id: str
    dataset_id: str | None = None
    materialization_type: MaterializationType = "auto"
    interval_hours: int = 6
    status: MaterializationStatus = "pending"
    last_run_at: str | None = None
    next_run_at: str | None = None
    error_message: str = ""
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class MaterializationResult(BaseModel):
    task_id: str
    object_id: str
    dataset_id: str
    status: MaterializationStatus
    row_count: int = 0
    run_duration_ms: float = 0.0
    error_message: str = ""
    completed_at: str = Field(default_factory=_now_iso)


class RowLevelPolicy(BaseModel):
    policy_id: str = Field(default_factory=lambda: f"rlp-{uuid.uuid4().hex[:8]}")
    view_id: str
    name: str
    policy_type: RowLevelPolicyType
    condition_expression: str
    status: RowLevelStatus = "active"
    description: str = ""
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class RowLevelEvaluationResult(BaseModel):
    policy_id: str
    view_id: str
    user_id: str
    passed: bool
    filtered_rows: int = 0
    total_rows: int = 0
    evaluated_at: str = Field(default_factory=_now_iso)


class ColumnLevelPolicy(BaseModel):
    policy_id: str = Field(default_factory=lambda: f"clp-{uuid.uuid4().hex[:8]}")
    mdo_id: str
    name: str
    policy_type: ColumnLevelPolicyType
    columns: list[str] = Field(default_factory=list)
    status: ColumnLevelStatus = "active"
    description: str = ""
    max_sources: int = 70
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class ColumnLevelEvaluationResult(BaseModel):
    policy_id: str
    mdo_id: str
    user_id: str
    accessible_columns: list[str]
    masked_columns: list[str]
    excluded_columns: list[str]
    source_count: int = 0
    evaluated_at: str = Field(default_factory=_now_iso)


class AgentTool(BaseModel):
    tool_id: str = Field(default_factory=lambda: f"at-{uuid.uuid4().hex[:8]}")
    name: str
    tool_type: ToolType
    description: str = ""
    schema: dict[str, Any] = Field(default_factory=dict)
    status: ToolStatus = "enabled"
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)


class ToolExecutionResult(BaseModel):
    tool_id: str
    tool_type: ToolType
    executed_by: str
    status: Literal["success", "failed"]
    output: dict[str, Any] = Field(default_factory=dict)
    error_message: str = ""
    execution_duration_ms: float = 0.0
    executed_at: str = Field(default_factory=_now_iso)


class MaterializationEngine:
    def __init__(self) -> None:
        self._tasks: dict[str, MaterializationTask] = {}
        self._lock = threading.Lock()

    def create_task(
        self, object_id: str, materialization_type: str = "auto", **kwargs: Any,
    ) -> MaterializationTask:
        if not object_id:
            raise MaterializationEngineError("MISSING_OBJECT_ID", "对象ID不能为空")
        if materialization_type not in {"auto", "manual", "scheduled"}:
            raise MaterializationEngineError(
                "INVALID_MATERIALIZATION_TYPE",
                f"未知物化类型：{materialization_type}",
            )
        task = MaterializationTask(object_id=object_id, materialization_type=materialization_type, **kwargs)
        with self._lock:
            if len(self._tasks) >= _MAX_ENTRIES:
                oldest_id = next(iter(self._tasks))
                self._tasks.pop(oldest_id, None)
            self._tasks[task.task_id] = task
        return task

    def get_task(self, task_id: str) -> MaterializationTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise MaterializationEngineError("NOT_FOUND", f"任务 {task_id} 不存在")
        return task

    def list_tasks(
        self,
        object_id: str | None = None,
        materialization_type: str | None = None,
        status: str | None = None,
    ) -> list[MaterializationTask]:
        items = list(self._tasks.values())
        if object_id:
            items = [t for t in items if t.object_id == object_id]
        if materialization_type:
            items = [t for t in items if t.materialization_type == materialization_type]
        if status:
            items = [t for t in items if t.status == status]
        return items

    def update_task(self, task_id: str, **kwargs: Any) -> MaterializationTask:
        task = self.get_task(task_id)
        for k, v in kwargs.items():
            if k in ("task_id", "created_at"):
                continue
            if k == "materialization_type" and v not in {"auto", "manual", "scheduled"}:
                raise MaterializationEngineError(
                    "INVALID_MATERIALIZATION_TYPE",
                    f"未知物化类型：{v}",
                )
            if k == "status" and v not in {"pending", "running", "completed", "failed"}:
                raise MaterializationEngineError(
                    "INVALID_STATUS",
                    f"未知状态：{v}",
                )
            if hasattr(task, k):
                setattr(task, k, v)
        task.updated_at = _now_iso()
        return task

    def delete_task(self, task_id: str) -> bool:
        with self._lock:
            return self._tasks.pop(task_id, None) is not None

    def run_materialization(self, task_id: str) -> MaterializationResult:
        task = self.get_task(task_id)
        task.status = "running"
        task.last_run_at = _now_iso()
        try:
            dataset_id = f"ds-{uuid.uuid4().hex[:12]}"
            row_count = hash(task.object_id) % 10000 + 1000
            duration_ms = abs(hash(task.object_id) % 5000)
            task.status = "completed"
            task.dataset_id = dataset_id
            task.next_run_at = _now_iso()
            return MaterializationResult(
                task_id=task_id,
                object_id=task.object_id,
                dataset_id=dataset_id,
                status="completed",
                row_count=row_count,
                run_duration_ms=duration_ms,
            )
        except Exception as exc:
            task.status = "failed"
            task.error_message = str(exc)
            return MaterializationResult(
                task_id=task_id,
                object_id=task.object_id,
                dataset_id="",
                status="failed",
                error_message=str(exc),
            )


class RowLevelEngine:
    def __init__(self) -> None:
        self._policies: dict[str, RowLevelPolicy] = {}
        self._lock = threading.Lock()

    def create_policy(
        self, view_id: str, name: str, policy_type: str, condition_expression: str, **kwargs: Any,
    ) -> RowLevelPolicy:
        if not view_id:
            raise RowLevelEngineError("MISSING_VIEW_ID", "视图ID不能为空")
        if not name:
            raise RowLevelEngineError("MISSING_NAME", "策略名称不能为空")
        if policy_type not in {"filter", "mask", "join"}:
            raise RowLevelEngineError("INVALID_POLICY_TYPE", f"未知策略类型：{policy_type}")
        policy = RowLevelPolicy(
            view_id=view_id,
            name=name,
            policy_type=policy_type,
            condition_expression=condition_expression,
            **kwargs,
        )
        with self._lock:
            if len(self._policies) >= _MAX_ENTRIES:
                oldest_id = next(iter(self._policies))
                self._policies.pop(oldest_id, None)
            self._policies[policy.policy_id] = policy
        return policy

    def get_policy(self, policy_id: str) -> RowLevelPolicy:
        policy = self._policies.get(policy_id)
        if policy is None:
            raise RowLevelEngineError("NOT_FOUND", f"策略 {policy_id} 不存在")
        return policy

    def list_policies(
        self,
        view_id: str | None = None,
        policy_type: str | None = None,
        status: str | None = None,
    ) -> list[RowLevelPolicy]:
        items = list(self._policies.values())
        if view_id:
            items = [p for p in items if p.view_id == view_id]
        if policy_type:
            items = [p for p in items if p.policy_type == policy_type]
        if status:
            items = [p for p in items if p.status == status]
        return items

    def update_policy(self, policy_id: str, **kwargs: Any) -> RowLevelPolicy:
        policy = self.get_policy(policy_id)
        for k, v in kwargs.items():
            if k in ("policy_id", "created_at"):
                continue
            if k == "policy_type" and v not in {"filter", "mask", "join"}:
                raise RowLevelEngineError("INVALID_POLICY_TYPE", f"未知策略类型：{v}")
            if k == "status" and v not in {"active", "inactive", "draft"}:
                raise RowLevelEngineError("INVALID_STATUS", f"未知状态：{v}")
            if hasattr(policy, k):
                setattr(policy, k, v)
        policy.updated_at = _now_iso()
        return policy

    def delete_policy(self, policy_id: str) -> bool:
        with self._lock:
            return self._policies.pop(policy_id, None) is not None

    def evaluate(self, policy_id: str, user_id: str) -> RowLevelEvaluationResult:
        policy = self.get_policy(policy_id)
        if policy.status != "active":
            return RowLevelEvaluationResult(
                policy_id=policy_id,
                view_id=policy.view_id,
                user_id=user_id,
                passed=True,
                filtered_rows=0,
                total_rows=0,
            )
        total_rows = hash(policy.view_id) % 1000 + 100
        passed = (hash(user_id + policy.policy_id) % 100) >= 20
        filtered_rows = total_rows if passed else total_rows - (hash(user_id) % 500)
        return RowLevelEvaluationResult(
            policy_id=policy_id,
            view_id=policy.view_id,
            user_id=user_id,
            passed=passed,
            filtered_rows=filtered_rows,
            total_rows=total_rows,
        )

    def evaluate_all(self, view_id: str, user_id: str) -> list[RowLevelEvaluationResult]:
        results: list[RowLevelEvaluationResult] = []
        for policy in self._policies.values():
            if policy.view_id == view_id:
                results.append(self.evaluate(policy.policy_id, user_id))
        return results


class ColumnLevelEngine:
    def __init__(self) -> None:
        self._policies: dict[str, ColumnLevelPolicy] = {}
        self._lock = threading.Lock()

    def create_policy(
        self, mdo_id: str, name: str, policy_type: str, **kwargs: Any,
    ) -> ColumnLevelPolicy:
        if not mdo_id:
            raise ColumnLevelEngineError("MISSING_MDO_ID", "MDO ID不能为空")
        if not name:
            raise ColumnLevelEngineError("MISSING_NAME", "策略名称不能为空")
        if policy_type not in {"include", "exclude", "mask", "encrypt"}:
            raise ColumnLevelEngineError("INVALID_POLICY_TYPE", f"未知策略类型：{policy_type}")
        columns = kwargs.get("columns", [])
        if not isinstance(columns, list):
            raise ColumnLevelEngineError("INVALID_COLUMNS", "columns 必须是列表")
        max_sources = kwargs.get("max_sources", 70)
        if max_sources > 70:
            raise ColumnLevelEngineError("MAX_SOURCES_EXCEEDED", "最大数据源数量不能超过70")
        policy = ColumnLevelPolicy(
            mdo_id=mdo_id,
            name=name,
            policy_type=policy_type,
            columns=columns,
            max_sources=max_sources,
            **kwargs,
        )
        with self._lock:
            if len(self._policies) >= _MAX_ENTRIES:
                oldest_id = next(iter(self._policies))
                self._policies.pop(oldest_id, None)
            self._policies[policy.policy_id] = policy
        return policy

    def get_policy(self, policy_id: str) -> ColumnLevelPolicy:
        policy = self._policies.get(policy_id)
        if policy is None:
            raise ColumnLevelEngineError("NOT_FOUND", f"策略 {policy_id} 不存在")
        return policy

    def list_policies(
        self,
        mdo_id: str | None = None,
        policy_type: str | None = None,
        status: str | None = None,
    ) -> list[ColumnLevelPolicy]:
        items = list(self._policies.values())
        if mdo_id:
            items = [p for p in items if p.mdo_id == mdo_id]
        if policy_type:
            items = [p for p in items if p.policy_type == policy_type]
        if status:
            items = [p for p in items if p.status == status]
        return items

    def update_policy(self, policy_id: str, **kwargs: Any) -> ColumnLevelPolicy:
        policy = self.get_policy(policy_id)
        for k, v in kwargs.items():
            if k in ("policy_id", "created_at"):
                continue
            if k == "policy_type" and v not in {"include", "exclude", "mask", "encrypt"}:
                raise ColumnLevelEngineError("INVALID_POLICY_TYPE", f"未知策略类型：{v}")
            if k == "status" and v not in {"active", "inactive", "draft"}:
                raise ColumnLevelEngineError("INVALID_STATUS", f"未知状态：{v}")
            if k == "max_sources" and v > 70:
                raise ColumnLevelEngineError("MAX_SOURCES_EXCEEDED", "最大数据源数量不能超过70")
            if hasattr(policy, k):
                setattr(policy, k, v)
        policy.updated_at = _now_iso()
        return policy

    def delete_policy(self, policy_id: str) -> bool:
        with self._lock:
            return self._policies.pop(policy_id, None) is not None

    def evaluate(self, policy_id: str, user_id: str) -> ColumnLevelEvaluationResult:
        policy = self.get_policy(policy_id)
        source_count = hash(policy.mdo_id) % policy.max_sources + 1
        if policy.status != "active":
            return ColumnLevelEvaluationResult(
                policy_id=policy_id,
                mdo_id=policy.mdo_id,
                user_id=user_id,
                accessible_columns=policy.columns.copy(),
                masked_columns=[],
                excluded_columns=[],
                source_count=source_count,
            )
        accessible: list[str] = []
        masked: list[str] = []
        excluded: list[str] = []
        for idx, col in enumerate(policy.columns):
            hash_val = hash(user_id + col) % 100
            if policy.policy_type == "include":
                accessible.append(col) if hash_val >= 30 else excluded.append(col)
            elif policy.policy_type == "exclude":
                excluded.append(col) if hash_val >= 30 else accessible.append(col)
            elif policy.policy_type == "mask":
                masked.append(col) if hash_val >= 50 else accessible.append(col)
            elif policy.policy_type == "encrypt":
                masked.append(col) if idx % 2 == 0 else accessible.append(col)
        return ColumnLevelEvaluationResult(
            policy_id=policy_id,
            mdo_id=policy.mdo_id,
            user_id=user_id,
            accessible_columns=accessible,
            masked_columns=masked,
            excluded_columns=excluded,
            source_count=source_count,
        )


class AgentToolsEngine:
    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}
        self._lock = threading.Lock()

    def create_tool(
        self, name: str, tool_type: str, **kwargs: Any,
    ) -> AgentTool:
        if not name:
            raise AgentToolsEngineError("MISSING_NAME", "工具名称不能为空")
        if tool_type not in {"Action", "Query", "Function", "Var", "Command", "Clarify"}:
            raise AgentToolsEngineError("INVALID_TOOL_TYPE", f"未知工具类型：{tool_type}")
        tool = AgentTool(name=name, tool_type=tool_type, **kwargs)
        with self._lock:
            if len(self._tools) >= _MAX_ENTRIES:
                oldest_id = next(iter(self._tools))
                self._tools.pop(oldest_id, None)
            self._tools[tool.tool_id] = tool
        return tool

    def get_tool(self, tool_id: str) -> AgentTool:
        tool = self._tools.get(tool_id)
        if tool is None:
            raise AgentToolsEngineError("NOT_FOUND", f"工具 {tool_id} 不存在")
        return tool

    def list_tools(
        self, tool_type: str | None = None, status: str | None = None,
    ) -> list[AgentTool]:
        items = list(self._tools.values())
        if tool_type:
            items = [t for t in items if t.tool_type == tool_type]
        if status:
            items = [t for t in items if t.status == status]
        return items

    def update_tool(self, tool_id: str, **kwargs: Any) -> AgentTool:
        tool = self.get_tool(tool_id)
        for k, v in kwargs.items():
            if k in ("tool_id", "created_at"):
                continue
            if k == "tool_type" and v not in {"Action", "Query", "Function", "Var", "Command", "Clarify"}:
                raise AgentToolsEngineError("INVALID_TOOL_TYPE", f"未知工具类型：{v}")
            if k == "status" and v not in {"enabled", "disabled"}:
                raise AgentToolsEngineError("INVALID_STATUS", f"未知状态：{v}")
            if hasattr(tool, k):
                setattr(tool, k, v)
        tool.updated_at = _now_iso()
        return tool

    def delete_tool(self, tool_id: str) -> bool:
        with self._lock:
            return self._tools.pop(tool_id, None) is not None

    def execute_tool(
        self, tool_id: str, executed_by: str, params: dict[str, Any] | None = None,
    ) -> ToolExecutionResult:
        tool = self.get_tool(tool_id)
        if tool.status != "enabled":
            return ToolExecutionResult(
                tool_id=tool_id,
                tool_type=tool.tool_type,
                executed_by=executed_by,
                status="failed",
                error_message="工具已禁用",
            )
        try:
            duration_ms = abs(hash(tool_id) % 3000)
            success = (hash(executed_by) % 100) >= 10
            output: dict[str, Any] = {}
            if tool.tool_type == "Action":
                output = {"action": "performed", "params": params or {}}
            elif tool.tool_type == "Query":
                output = {"query": "executed", "results": []}
            elif tool.tool_type == "Function":
                output = {"function": "called", "return_value": "OK"}
            elif tool.tool_type == "Var":
                output = {"variable": "resolved", "value": "test_value"}
            elif tool.tool_type == "Command":
                output = {"command": "executed", "exit_code": 0}
            elif tool.tool_type == "Clarify":
                output = {"clarification": "provided", "response": "Yes"}
            return ToolExecutionResult(
                tool_id=tool_id,
                tool_type=tool.tool_type,
                executed_by=executed_by,
                status="success" if success else "failed",
                output=output if success else {},
                error_message="" if success else "执行失败",
                execution_duration_ms=duration_ms,
            )
        except Exception as exc:
            return ToolExecutionResult(
                tool_id=tool_id,
                tool_type=tool.tool_type,
                executed_by=executed_by,
                status="failed",
                error_message=str(exc),
            )

    def get_tool_types(self) -> list[ToolType]:
        return ["Action", "Query", "Function", "Var", "Command", "Clarify"]


_materialization_engine: MaterializationEngine | None = None
_row_level_engine: RowLevelEngine | None = None
_column_level_engine: ColumnLevelEngine | None = None
_agent_tools_engine: AgentToolsEngine | None = None
_singleton_lock = threading.Lock()


def get_materialization_engine() -> MaterializationEngine:
    global _materialization_engine
    if _materialization_engine is None:
        with _singleton_lock:
            if _materialization_engine is None:
                _materialization_engine = MaterializationEngine()
    return _materialization_engine


def get_row_level_engine() -> RowLevelEngine:
    global _row_level_engine
    if _row_level_engine is None:
        with _singleton_lock:
            if _row_level_engine is None:
                _row_level_engine = RowLevelEngine()
    return _row_level_engine


def get_column_level_engine() -> ColumnLevelEngine:
    global _column_level_engine
    if _column_level_engine is None:
        with _singleton_lock:
            if _column_level_engine is None:
                _column_level_engine = ColumnLevelEngine()
    return _column_level_engine


def get_agent_tools_engine() -> AgentToolsEngine:
    global _agent_tools_engine
    if _agent_tools_engine is None:
        with _singleton_lock:
            if _agent_tools_engine is None:
                _agent_tools_engine = AgentToolsEngine()
    return _agent_tools_engine