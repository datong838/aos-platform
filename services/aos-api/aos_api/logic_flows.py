"""W2-AF · 逻辑流与 Data Connection Agent 组（#111 / #112 / #113）.

- #111 LogicFlowEngine：逻辑流编排（compass_files_lister/connector/join/transform 4 步骤）
- #112 AgentProxyEngine：内网反向代理运行时（online/offline/draining 3 态 + heartbeat + forward_request）
- #113 AgentWorkerEngine：客户主机执行运行时（registered/online/offline/failed 4 态 + assign_job + complete_job）

详见 docs/palantier/20_tech/220tech_w2-af-logic-flows.md。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

# ════════════════════ 常量 ════════════════════

_VALID_STEP_KINDS = {"compass_files_lister", "connector", "join", "transform"}
_VALID_FLOW_STATUSES = {"draft", "running", "completed", "error"}
_VALID_EXEC_STATUSES = {"running", "completed", "error"}

_VALID_PROXY_STATUSES = {"online", "offline", "draining"}

_VALID_WORKER_STATUSES = {"registered", "online", "offline", "failed"}
_VALID_JOB_STATUSES = {"assigned", "running", "completed", "failed"}

_MAX_FLOWS = 200
_MAX_EXECUTIONS = 200
_MAX_PROXIES = 200
_MAX_WORKERS = 200
_MAX_JOBS = 200


# ════════════════════ 数据模型 ════════════════════

class FlowStep(BaseModel):
    """逻辑流步骤。"""
    id: str = Field(default_factory=lambda: "step-" + uuid.uuid4().hex[:8])
    kind: str                            # compass_files_lister / connector / join / transform
    name: str = ""
    config: dict[str, Any] = Field(default_factory=dict)
    next_step_id: str = ""


class LogicFlow(BaseModel):
    """逻辑流定义。"""
    id: str = Field(default_factory=lambda: "lf-" + uuid.uuid4().hex[:10])
    name: str
    description: str = ""
    steps: list[FlowStep] = Field(default_factory=list)
    status: str = "draft"                # draft / running / completed / error
    created_at: float = Field(default_factory=lambda: time.time())


class FlowExecution(BaseModel):
    """逻辑流执行记录。"""
    id: str = Field(default_factory=lambda: "exec-" + uuid.uuid4().hex[:10])
    flow_id: str
    status: str = "running"              # running / completed / error
    step_results: list[dict[str, Any]] = Field(default_factory=list)
    started_at: float = Field(default_factory=lambda: time.time())
    completed_at: float = 0.0


class AgentProxy(BaseModel):
    """内网反向代理运行时。"""
    id: str = Field(default_factory=lambda: "ap-" + uuid.uuid4().hex[:10])
    name: str
    agent_id: str
    proxy_url: str
    auth_token: str = ""
    status: str = "offline"              # online / offline / draining
    connections: int = 0
    last_heartbeat: float = 0.0
    created_at: float = Field(default_factory=lambda: time.time())


class AgentWorker(BaseModel):
    """客户主机执行运行时。"""
    id: str = Field(default_factory=lambda: "aw-" + uuid.uuid4().hex[:10])
    agent_id: str
    host: str
    version: str = "1.0.0"
    status: str = "registered"           # registered / online / offline / failed
    capabilities: list[str] = Field(default_factory=list)
    last_heartbeat: float = 0.0
    job_ids: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())


class WorkerJob(BaseModel):
    """Worker 任务。"""
    id: str = Field(default_factory=lambda: "job-" + uuid.uuid4().hex[:10])
    worker_id: str
    capability: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "assigned"             # assigned / running / completed / failed
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=lambda: time.time())
    completed_at: float = 0.0


# ════════════════════ 错误 ════════════════════

class LogicFlowsError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════ #111 LogicFlowEngine ════════════════════

class LogicFlowEngine:
    def __init__(self) -> None:
        self._flows: dict[str, LogicFlow] = {}
        self._executions: list[FlowExecution] = []
        self._lock = threading.Lock()

    def register(self, flow: LogicFlow) -> LogicFlow:
        if not flow.name:
            raise LogicFlowsError("MISSING_NAME", "逻辑流名称不能为空")
        for step in flow.steps:
            if step.kind not in _VALID_STEP_KINDS:
                raise LogicFlowsError("INVALID_STEP_KIND", f"未知步骤类型：{step.kind}")
        with self._lock:
            if len(self._flows) >= _MAX_FLOWS:
                oldest_id = next(iter(self._flows))
                self._flows.pop(oldest_id, None)
            self._flows[flow.id] = flow
        return flow

    def get(self, flow_id: str) -> LogicFlow:
        f = self._flows.get(flow_id)
        if f is None:
            raise LogicFlowsError("NOT_FOUND", f"逻辑流 {flow_id} 不存在")
        return f

    def list(self, status: str | None = None) -> list[LogicFlow]:
        items = list(self._flows.values())
        if status:
            items = [f for f in items if f.status == status]
        return items

    def update(self, flow_id: str, updates: dict[str, Any]) -> LogicFlow:
        f = self.get(flow_id)
        for k, v in updates.items():
            if k in ("id", "created_at"):
                continue
            if k == "steps" and isinstance(v, list):
                for step in v:
                    kind = step.kind if hasattr(step, "kind") else step.get("kind", "")
                    if kind not in _VALID_STEP_KINDS:
                        raise LogicFlowsError("INVALID_STEP_KIND", f"未知步骤类型：{kind}")
            if hasattr(f, k):
                setattr(f, k, v)
        return f

    def delete(self, flow_id: str) -> bool:
        return self._flows.pop(flow_id, None) is not None

    def execute(self, flow_id: str) -> FlowExecution:
        f = self.get(flow_id)
        execution = FlowExecution(flow_id=flow_id, status="running")
        f.status = "running"
        step_results: list[dict[str, Any]] = []
        prev_output: Any = None
        try:
            for step in f.steps:
                result = self._run_step(step, prev_output)
                step_results.append(result)
                if result["status"] == "error":
                    execution.status = "error"
                    execution.step_results = step_results
                    execution.completed_at = time.time()
                    f.status = "error"
                    self._append_execution(execution)
                    return execution
                prev_output = result.get("output")
            execution.status = "completed"
            execution.step_results = step_results
            execution.completed_at = time.time()
            f.status = "completed"
        except LogicFlowsError:
            raise
        except Exception as exc:  # noqa: BLE001
            execution.status = "error"
            execution.step_results = step_results
            execution.completed_at = time.time()
            f.status = "error"
            execution.step_results.append({
                "step_id": "unknown",
                "kind": "unknown",
                "status": "error",
                "error": str(exc),
            })
        self._append_execution(execution)
        return execution

    def _run_step(self, step: FlowStep, prev_output: Any) -> dict[str, Any]:
        try:
            if step.kind == "compass_files_lister":
                files = step.config.get("files", [])
                return {
                    "step_id": step.id, "kind": step.kind,
                    "status": "completed", "output": files,
                }
            if step.kind == "connector":
                conn = step.config.get("connection", "ok")
                return {
                    "step_id": step.id, "kind": step.kind,
                    "status": "completed", "output": conn,
                }
            if step.kind == "join":
                # 合并前步结果（若是 list）+ config.lists
                merged: list[Any] = []
                if isinstance(prev_output, list):
                    merged.extend(prev_output)
                for lst in step.config.get("lists", []):
                    if isinstance(lst, list):
                        merged.extend(lst)
                return {
                    "step_id": step.id, "kind": step.kind,
                    "status": "completed", "output": merged,
                }
            if step.kind == "transform":
                transformed = step.config.get("transformed", "ok")
                return {
                    "step_id": step.id, "kind": step.kind,
                    "status": "completed", "output": transformed,
                }
            return {
                "step_id": step.id, "kind": step.kind,
                "status": "error", "error": f"未知步骤类型：{step.kind}",
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "step_id": step.id, "kind": step.kind,
                "status": "error", "error": str(exc),
            }

    def _append_execution(self, execution: FlowExecution) -> None:
        with self._lock:
            if len(self._executions) >= _MAX_EXECUTIONS:
                self._executions.pop(0)
            self._executions.append(execution)

    def list_executions(
        self, flow_id: str | None = None, limit: int = 50,
    ) -> list[FlowExecution]:
        items = list(self._executions)
        if flow_id:
            items = [e for e in items if e.flow_id == flow_id]
        items = list(reversed(items))
        if limit > 0:
            items = items[:limit]
        return items


# ════════════════════ #112 AgentProxyEngine ════════════════════

class AgentProxyEngine:
    def __init__(self) -> None:
        self._proxies: dict[str, AgentProxy] = {}
        self._lock = threading.Lock()

    def register(self, proxy: AgentProxy) -> AgentProxy:
        if not proxy.name:
            raise LogicFlowsError("MISSING_NAME", "代理名称不能为空")
        if not proxy.agent_id:
            raise LogicFlowsError("MISSING_AGENT", "agent_id 不能为空")
        if not proxy.proxy_url:
            raise LogicFlowsError("MISSING_URL", "proxy_url 不能为空")
        with self._lock:
            if len(self._proxies) >= _MAX_PROXIES:
                oldest_id = next(iter(self._proxies))
                self._proxies.pop(oldest_id, None)
            self._proxies[proxy.id] = proxy
        return proxy

    def get(self, proxy_id: str) -> AgentProxy:
        p = self._proxies.get(proxy_id)
        if p is None:
            raise LogicFlowsError("NOT_FOUND", f"代理 {proxy_id} 不存在")
        return p

    def list(
        self, status: str | None = None, agent_id: str | None = None,
    ) -> list[AgentProxy]:
        items = list(self._proxies.values())
        if status:
            items = [p for p in items if p.status == status]
        if agent_id:
            items = [p for p in items if p.agent_id == agent_id]
        return items

    def update(self, proxy_id: str, updates: dict[str, Any]) -> AgentProxy:
        p = self.get(proxy_id)
        for k, v in updates.items():
            if k in ("id", "created_at"):
                continue
            if hasattr(p, k):
                setattr(p, k, v)
        return p

    def delete(self, proxy_id: str) -> bool:
        return self._proxies.pop(proxy_id, None) is not None

    def heartbeat(self, proxy_id: str) -> AgentProxy:
        p = self.get(proxy_id)
        p.last_heartbeat = time.time()
        p.status = "online"
        return p

    def drain(self, proxy_id: str) -> AgentProxy:
        p = self.get(proxy_id)
        p.status = "draining"
        return p

    def forward_request(
        self, proxy_id: str, request: dict[str, Any],
    ) -> dict[str, Any]:
        p = self.get(proxy_id)
        if p.status != "online":
            raise LogicFlowsError(
                "PROXY_UNAVAILABLE", f"代理状态为 {p.status}，无法转发",
            )
        p.connections += 1
        try:
            # 模拟转发
            response = {
                "status_code": 200,
                "body": {"ok": True, "echo": request},
            }
            return {"forwarded": True, "response": response}
        finally:
            p.connections -= 1


# ════════════════════ #113 AgentWorkerEngine ════════════════════

class AgentWorkerEngine:
    def __init__(self) -> None:
        self._workers: dict[str, AgentWorker] = {}
        self._jobs: dict[str, WorkerJob] = {}
        self._lock = threading.Lock()

    def register(self, worker: AgentWorker) -> AgentWorker:
        if not worker.agent_id:
            raise LogicFlowsError("MISSING_AGENT", "agent_id 不能为空")
        if not worker.host:
            raise LogicFlowsError("MISSING_HOST", "host 不能为空")
        with self._lock:
            if len(self._workers) >= _MAX_WORKERS:
                oldest_id = next(iter(self._workers))
                self._workers.pop(oldest_id, None)
            self._workers[worker.id] = worker
        return worker

    def get(self, worker_id: str) -> AgentWorker:
        w = self._workers.get(worker_id)
        if w is None:
            raise LogicFlowsError("NOT_FOUND", f"Worker {worker_id} 不存在")
        return w

    def list(
        self, status: str | None = None, agent_id: str | None = None,
    ) -> list[AgentWorker]:
        items = list(self._workers.values())
        if status:
            items = [w for w in items if w.status == status]
        if agent_id:
            items = [w for w in items if w.agent_id == agent_id]
        return items

    def update(self, worker_id: str, updates: dict[str, Any]) -> AgentWorker:
        w = self.get(worker_id)
        for k, v in updates.items():
            if k in ("id", "created_at"):
                continue
            if hasattr(w, k):
                setattr(w, k, v)
        return w

    def delete(self, worker_id: str) -> bool:
        return self._workers.pop(worker_id, None) is not None

    def heartbeat(self, worker_id: str) -> AgentWorker:
        w = self.get(worker_id)
        w.last_heartbeat = time.time()
        w.status = "online"
        return w

    def assign_job(
        self, worker_id: str, capability: str, payload: dict[str, Any],
    ) -> WorkerJob:
        w = self.get(worker_id)
        if w.status != "online":
            raise LogicFlowsError(
                "WORKER_OFFLINE", f"Worker 状态为 {w.status}，无法分配任务",
            )
        if capability not in w.capabilities:
            raise LogicFlowsError(
                "CAPABILITY_NOT_SUPPORTED",
                f"Worker 不支持能力：{capability}",
            )
        job = WorkerJob(
            worker_id=worker_id, capability=capability, payload=payload,
        )
        with self._lock:
            if len(self._jobs) >= _MAX_JOBS:
                oldest_id = next(iter(self._jobs))
                self._jobs.pop(oldest_id, None)
            self._jobs[job.id] = job
            w.job_ids.append(job.id)
        return job

    def complete_job(
        self, job_id: str, result: dict[str, Any],
    ) -> WorkerJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise LogicFlowsError("NOT_FOUND", f"任务 {job_id} 不存在")
        if job.status == "completed":
            raise LogicFlowsError("ALREADY_COMPLETED", f"任务 {job_id} 已完成")
        job.status = "completed"
        job.result = result
        job.completed_at = time.time()
        return job

    def list_jobs(
        self, worker_id: str | None = None, status: str | None = None,
    ) -> list[WorkerJob]:
        items = list(self._jobs.values())
        if worker_id:
            items = [j for j in items if j.worker_id == worker_id]
        if status:
            items = [j for j in items if j.status == status]
        return items


# ════════════════════ 单例 ════════════════════

_flow_engine: LogicFlowEngine | None = None
_proxy_engine: AgentProxyEngine | None = None
_worker_engine: AgentWorkerEngine | None = None
_singleton_lock = threading.Lock()


def get_flow_engine() -> LogicFlowEngine:
    global _flow_engine
    if _flow_engine is None:
        with _singleton_lock:
            if _flow_engine is None:
                _flow_engine = LogicFlowEngine()
    return _flow_engine


def get_proxy_engine() -> AgentProxyEngine:
    global _proxy_engine
    if _proxy_engine is None:
        with _singleton_lock:
            if _proxy_engine is None:
                _proxy_engine = AgentProxyEngine()
    return _proxy_engine


def get_worker_engine() -> AgentWorkerEngine:
    global _worker_engine
    if _worker_engine is None:
        with _singleton_lock:
            if _worker_engine is None:
                _worker_engine = AgentWorkerEngine()
    return _worker_engine
