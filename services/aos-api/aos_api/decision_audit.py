"""W2-X · AIP 决策审计组：#84 Decision Lineage + #85 Insight Backfill + #87 Capability Adapter 契约.

本模块是 AIP 决策侧的可观测与重能力契约层三件：
    - DecisionLineageEngine   完整决策记录（8+ 字段）+ 时间线 + 溯源 API
    - InsightBackfillEngine   高置信结论 → Insight Object + 阈值控制 + 回填
    - CapabilityAdapterEngine Manifest CRUD + C0/C1/C2 分级 + 运行时 API（invoke/submit/status/cancel/artifact/session）

不重写 Drafts/Wiki/MediaSet；仅作审计与契约层。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────
# 公共工具
# ────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class DecisionAuditError(Exception):
    """W2-X AIP 决策审计组错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════════════════════════════════════════════════
# #84 Decision Lineage
# ════════════════════════════════════════════════════════════════

class DecisionRecord(BaseModel):
    """决策记录（对齐 220w §6.4）。"""

    id: str = Field(default_factory=lambda: _uid("dec"))
    timestamp: float = Field(default_factory=_now_ts)
    logic_id: str
    proposal_id: str = ""             # 关联 W2-W ProposalSubmission
    model_id: str = ""                # 选用模型
    prompt_version: str = ""          # Prompt 版本
    object_refs: list[str] = Field(default_factory=list)  # 读取的 Object 引用
    wiki_fields: list[str] = Field(default_factory=list)  # 读取的 Wiki 字段
    cot: str = ""                     # CoT 思维链
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)  # Tool 调用序列
    draft_params: dict[str, Any] = Field(default_factory=dict)      # Draft 参数
    approval_result: str = ""         # 审批结果 approved/rejected/pending
    actor: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


_MAX_RECORDS = 200


class DecisionLineageEngine:
    """#84 · 决策谱系引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, DecisionRecord] = {}
        self._order: list[str] = []  # 按 record 顺序保留

    def record(self, rec: DecisionRecord) -> DecisionRecord:
        with self._lock:
            # 若 id 已存在则覆盖；否则新增
            is_new = rec.id not in self._records
            self._records[rec.id] = rec
            if is_new:
                self._order.append(rec.id)
            # 200 条上限：淘汰最早的
            while len(self._order) > _MAX_RECORDS:
                old_id = self._order.pop(0)
                self._records.pop(old_id, None)
        return rec

    def get(self, decision_id: str) -> DecisionRecord:
        with self._lock:
            rec = self._records.get(decision_id)
        if not rec:
            raise DecisionAuditError(
                "NOT_FOUND",
                f"决策记录 {decision_id} 不存在",
            )
        return rec

    def list(
        self,
        logic_id: str | None = None,
        proposal_id: str | None = None,
        actor: str | None = None,
        limit: int = 50,
    ) -> list[DecisionRecord]:
        with self._lock:
            items = [self._records[i] for i in self._order]
        if logic_id:
            items = [r for r in items if r.logic_id == logic_id]
        if proposal_id:
            items = [r for r in items if r.proposal_id == proposal_id]
        if actor:
            items = [r for r in items if r.actor == actor]
        # 按时间倒序
        items = sorted(items, key=lambda r: r.timestamp, reverse=True)
        return items[:limit]

    def get_timeline(self, decision_id: str) -> dict[str, Any]:
        """返回决策时间线（按时间排序的 Tool 调用 + 审批事件）。"""
        rec = self.get(decision_id)
        events: list[dict[str, Any]] = []
        # Tool 调用事件
        for idx, call in enumerate(rec.tool_calls):
            events.append({
                "seq": idx,
                "type": "tool_call",
                "timestamp": rec.timestamp + idx * 0.001,  # 保持顺序
                "detail": call,
            })
        # 审批事件（如果有）
        if rec.approval_result:
            events.append({
                "seq": len(rec.tool_calls),
                "type": "approval",
                "timestamp": rec.timestamp + len(rec.tool_calls) * 0.001,
                "detail": {"result": rec.approval_result, "actor": rec.actor},
            })
        return {
            "decision_id": rec.id,
            "logic_id": rec.logic_id,
            "started_at": rec.timestamp,
            "events": events,
        }

    def trace(self, proposal_id: str) -> list[DecisionRecord]:
        """按提案溯源（一个提案可能多条决策记录）。"""
        with self._lock:
            items = [self._records[i] for i in self._order]
        items = [r for r in items if r.proposal_id == proposal_id]
        return sorted(items, key=lambda r: r.timestamp)


# ════════════════════════════════════════════════════════════════
# #85 Insight Backfill
# ════════════════════════════════════════════════════════════════

class InsightObject(BaseModel):
    """Insight 对象（对齐 T07 §5 / 220w §6.4）。"""

    id: str = Field(default_factory=lambda: _uid("ins"))
    title: str
    content: str
    confidence: float                  # 0~1
    source_decision_id: str            # 来源决策记录
    object_type: str = "Insight"
    object_id: str = ""
    links: list[str] = Field(default_factory=list)  # 关联 Ontology 对象 RID
    created_at: float = Field(default_factory=_now_ts)
    backfill_status: str = "pending"   # pending / completed / failed


class BackfillConfig(BaseModel):
    """回填配置。"""

    confidence_threshold: float = 0.85  # 高置信阈值
    auto_backfill: bool = False          # 是否自动回填
    max_daily_backfill: int = 100        # 每日上限


_MAX_INSIGHTS = 200


class InsightBackfillEngine:
    """#85 · Insight 回填引擎。"""

    def __init__(self, config: BackfillConfig | None = None) -> None:
        self._lock = threading.Lock()
        self._config = config or BackfillConfig()
        self._insights: dict[str, InsightObject] = {}
        self._order: list[str] = []

    def get_config(self) -> BackfillConfig:
        with self._lock:
            return self._config.model_copy()

    def update_config(self, cfg: BackfillConfig) -> BackfillConfig:
        if not (0.0 <= cfg.confidence_threshold <= 1.0):
            raise DecisionAuditError(
                "INVALID_THRESHOLD",
                f"confidence_threshold 必须在 [0,1]: {cfg.confidence_threshold}",
            )
        if cfg.max_daily_backfill < 0:
            raise DecisionAuditError(
                "INVALID_LIMIT",
                f"max_daily_backfill 不能为负: {cfg.max_daily_backfill}",
            )
        with self._lock:
            self._config = cfg
        return cfg.model_copy()

    def register_insight(self, ins: InsightObject) -> InsightObject:
        if not (0.0 <= ins.confidence <= 1.0):
            raise DecisionAuditError(
                "INVALID_CONFIDENCE",
                f"confidence 必须在 [0,1]: {ins.confidence}",
            )
        with self._lock:
            is_new = ins.id not in self._insights
            self._insights[ins.id] = ins
            if is_new:
                self._order.append(ins.id)
            while len(self._order) > _MAX_INSIGHTS:
                old_id = self._order.pop(0)
                self._insights.pop(old_id, None)
        return ins

    def get_insight(self, insight_id: str) -> InsightObject:
        with self._lock:
            ins = self._insights.get(insight_id)
        if not ins:
            raise DecisionAuditError(
                "NOT_FOUND",
                f"Insight {insight_id} 不存在",
            )
        return ins

    def list_insights(
        self,
        source_decision_id: str | None = None,
        backfill_status: str | None = None,
        min_confidence: float = 0.0,
        limit: int = 50,
    ) -> list[InsightObject]:
        with self._lock:
            items = [self._insights[i] for i in self._order]
        if source_decision_id:
            items = [i for i in items if i.source_decision_id == source_decision_id]
        if backfill_status:
            items = [i for i in items if i.backfill_status == backfill_status]
        if min_confidence > 0.0:
            items = [i for i in items if i.confidence >= min_confidence]
        items = sorted(items, key=lambda r: r.created_at, reverse=True)
        return items[:limit]

    def backfill(self, insight_id: str) -> InsightObject:
        """执行回填：标记 backfill_status=completed；简化版不实际写回 Ontology。"""
        with self._lock:
            ins = self._insights.get(insight_id)
            if not ins:
                raise DecisionAuditError(
                    "NOT_FOUND",
                    f"Insight {insight_id} 不存在",
                )
            if ins.backfill_status == "completed":
                raise DecisionAuditError(
                    "ALREADY_BACKFILLED",
                    f"Insight {insight_id} 已回填",
                )
            # 简化版：仅标记为 completed
            ins.backfill_status = "completed"
            self._insights[insight_id] = ins
            return ins.model_copy()

    def evaluate_and_register(
        self,
        decision_id: str,
        title: str,
        content: str,
        confidence: float,
        links: list[str] | None = None,
    ) -> InsightObject:
        """评估置信度并注册 Insight（>= threshold 才注册）。"""
        with self._lock:
            threshold = self._config.confidence_threshold
        if confidence < threshold:
            raise DecisionAuditError(
                "BELOW_THRESHOLD",
                f"confidence {confidence} 低于阈值 {threshold}",
            )
        ins = InsightObject(
            title=title,
            content=content,
            confidence=confidence,
            source_decision_id=decision_id,
            links=links or [],
        )
        return self.register_insight(ins)

    def list_pending(self, limit: int = 50) -> list[InsightObject]:
        return self.list_insights(backfill_status="pending", limit=limit)

    def cleanup(self) -> int:
        """清理 backfill_status=failed 的旧记录。"""
        with self._lock:
            failed_ids = [
                iid for iid in self._order
                if self._insights[iid].backfill_status == "failed"
            ]
            for iid in failed_ids:
                self._insights.pop(iid, None)
                self._order.remove(iid)
            return len(failed_ids)


# ════════════════════════════════════════════════════════════════
# #87 Capability Adapter
# ════════════════════════════════════════════════════════════════

class AdapterManifest(BaseModel):
    """Capability Adapter Manifest（对齐 07b §3）。"""

    id: str
    name: str
    capability_class: str             # C0 同步 / C1 异步 Job / C2 长会话
    version: str = "1.0.0"
    description: str = ""
    invoke_endpoint: str = ""         # C0 invoke 端点
    submit_endpoint: str = ""         # C1 submit 端点
    status_endpoint: str = ""         # C1 status 端点
    cancel_endpoint: str = ""         # C1 cancel 端点
    artifact_endpoint: str = ""       # C1 artifact 端点
    session_open_endpoint: str = ""   # C2 session.open 端点
    session_close_endpoint: str = ""  # C2 session.close 端点
    auth_type: str = "none"           # none / bearer / basic / hmac
    enabled: bool = True
    registered_at: float = Field(default_factory=_now_ts)


class AdapterInvocation(BaseModel):
    """Capability Adapter 调用记录。"""

    id: str = Field(default_factory=lambda: _uid("inv"))
    adapter_id: str
    capability_class: str             # C0 / C1 / C2
    operation: str                    # invoke / submit / status / cancel / artifact / session.open / session.close
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    job_id: str = ""                  # C1 异步 Job ID
    session_id: str = ""              # C2 Session ID
    status: str = "pending"           # pending / running / completed / failed / cancelled
    started_at: float = Field(default_factory=_now_ts)
    ended_at: float = 0.0
    error: str = ""


_VALID_CAPABILITY_CLASSES = {"C0", "C1", "C2"}
_VALID_AUTH_TYPES = {"none", "bearer", "basic", "hmac"}
_VALID_OPERATIONS = {
    "invoke", "submit", "status", "cancel", "artifact",
    "session.open", "session.close",
}
_OPERATION_BY_CLASS: dict[str, set[str]] = {
    "C0": {"invoke"},
    "C1": {"submit", "status", "cancel", "artifact"},
    "C2": {"session.open", "session.close"},
}

_MAX_INVOCATIONS = 200


class CapabilityAdapterEngine:
    """#87 · Capability Adapter 引擎（Facade 层）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._adapters: dict[str, AdapterManifest] = {}
        self._invocations: dict[str, AdapterInvocation] = {}
        self._inv_order: list[str] = []

    # —— Manifest CRUD ——
    def register(self, manifest: AdapterManifest) -> AdapterManifest:
        if manifest.capability_class not in _VALID_CAPABILITY_CLASSES:
            raise DecisionAuditError(
                "INVALID_CLASS",
                f"未知 capability_class: {manifest.capability_class}（合法: {sorted(_VALID_CAPABILITY_CLASSES)}）",
            )
        if manifest.auth_type not in _VALID_AUTH_TYPES:
            raise DecisionAuditError(
                "INVALID_AUTH_TYPE",
                f"未知 auth_type: {manifest.auth_type}（合法: {sorted(_VALID_AUTH_TYPES)}）",
            )
        with self._lock:
            self._adapters[manifest.id] = manifest
        return manifest

    def get(self, adapter_id: str) -> AdapterManifest:
        with self._lock:
            m = self._adapters.get(adapter_id)
        if not m:
            raise DecisionAuditError(
                "NOT_FOUND",
                f"Adapter {adapter_id} 不存在",
            )
        return m

    def list(
        self,
        capability_class: str | None = None,
        enabled_only: bool = False,
    ) -> list[AdapterManifest]:
        with self._lock:
            items = list(self._adapters.values())
        if capability_class:
            items = [m for m in items if m.capability_class == capability_class]
        if enabled_only:
            items = [m for m in items if m.enabled]
        return sorted(items, key=lambda m: m.registered_at, reverse=True)

    def update(self, adapter_id: str, updates: dict[str, Any]) -> AdapterManifest:
        # 禁止改 capability_class（破坏契约）
        if "capability_class" in updates:
            raise DecisionAuditError(
                "IMMUTABLE_FIELD",
                "capability_class 不可修改（请重新注册新 Adapter）",
            )
        if "auth_type" in updates and updates["auth_type"] not in _VALID_AUTH_TYPES:
            raise DecisionAuditError(
                "INVALID_AUTH_TYPE",
                f"未知 auth_type: {updates['auth_type']}",
            )
        with self._lock:
            m = self._adapters.get(adapter_id)
            if not m:
                raise DecisionAuditError(
                    "NOT_FOUND",
                    f"Adapter {adapter_id} 不存在",
                )
            data = m.model_dump()
            for k, v in updates.items():
                if k in data and k != "id":
                    data[k] = v
            updated = AdapterManifest(**data)
            self._adapters[adapter_id] = updated
            return updated.model_copy()

    def delete(self, adapter_id: str) -> bool:
        with self._lock:
            return self._adapters.pop(adapter_id, None) is not None

    # —— 内部辅助 ——
    def _check_adapter(self, adapter_id: str, expected_class: str) -> AdapterManifest:
        """校验 adapter 存在 + 启用 + class 匹配。"""
        m = self.get(adapter_id)
        if not m.enabled:
            raise DecisionAuditError(
                "ADAPTER_DISABLED",
                f"Adapter {adapter_id} 已禁用",
            )
        if m.capability_class != expected_class:
            raise DecisionAuditError(
                "INVALID_CLASS",
                f"Adapter {adapter_id} 为 {m.capability_class}，期望 {expected_class}",
            )
        return m

    def _add_invocation(self, inv: AdapterInvocation) -> None:
        with self._lock:
            is_new = inv.id not in self._invocations
            self._invocations[inv.id] = inv
            if is_new:
                self._inv_order.append(inv.id)
            while len(self._inv_order) > _MAX_INVOCATIONS:
                old_id = self._inv_order.pop(0)
                self._invocations.pop(old_id, None)

    # —— C0 同步 ——
    def invoke(
        self,
        adapter_id: str,
        inputs: dict[str, Any],
        invoke_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> AdapterInvocation:
        """C0 同步调用：立即返回结果。"""
        self._check_adapter(adapter_id, "C0")
        inv = AdapterInvocation(
            adapter_id=adapter_id,
            capability_class="C0",
            operation="invoke",
            inputs=inputs,
            status="running",
        )
        self._add_invocation(inv)
        try:
            outputs = invoke_callable(inputs) if invoke_callable else {"echo": inputs}
            inv.outputs = outputs
            inv.status = "completed"
            inv.ended_at = _now_ts()
        except Exception as exc:  # noqa: BLE001
            inv.status = "failed"
            inv.error = str(exc)
            inv.ended_at = _now_ts()
        self._add_invocation(inv)
        return inv

    # —— C1 异步 Job ——
    def submit(
        self,
        adapter_id: str,
        inputs: dict[str, Any],
        submit_callable: Callable[[dict[str, Any]], str] | None = None,
    ) -> AdapterInvocation:
        """C1 异步提交：返回 job_id。"""
        self._check_adapter(adapter_id, "C1")
        job_id = submit_callable(inputs) if submit_callable else _uid("job")
        inv = AdapterInvocation(
            adapter_id=adapter_id,
            capability_class="C1",
            operation="submit",
            inputs=inputs,
            job_id=job_id,
            status="running",
        )
        self._add_invocation(inv)
        return inv

    def status(
        self,
        adapter_id: str,
        job_id: str,
        status_callable: Callable[[str], str] | None = None,
    ) -> AdapterInvocation:
        """C1 查询 job 状态。"""
        self._check_adapter(adapter_id, "C1")
        new_status = status_callable(job_id) if status_callable else "running"
        if new_status not in {"pending", "running", "completed", "failed", "cancelled"}:
            raise DecisionAuditError(
                "INVALID_STATUS",
                f"未知 job status: {new_status}",
            )
        inv = AdapterInvocation(
            adapter_id=adapter_id,
            capability_class="C1",
            operation="status",
            job_id=job_id,
            status=new_status,
        )
        self._add_invocation(inv)
        return inv

    def cancel(self, adapter_id: str, job_id: str) -> AdapterInvocation:
        """C1 取消 job。"""
        self._check_adapter(adapter_id, "C1")
        inv = AdapterInvocation(
            adapter_id=adapter_id,
            capability_class="C1",
            operation="cancel",
            job_id=job_id,
            status="cancelled",
            ended_at=_now_ts(),
        )
        self._add_invocation(inv)
        return inv

    def artifact(
        self,
        adapter_id: str,
        job_id: str,
        artifact_callable: Callable[[str], dict[str, Any]] | None = None,
    ) -> AdapterInvocation:
        """C1 获取 job 产物。"""
        self._check_adapter(adapter_id, "C1")
        outputs = artifact_callable(job_id) if artifact_callable else {"job_id": job_id}
        inv = AdapterInvocation(
            adapter_id=adapter_id,
            capability_class="C1",
            operation="artifact",
            job_id=job_id,
            outputs=outputs,
            status="completed",
            ended_at=_now_ts(),
        )
        self._add_invocation(inv)
        return inv

    # —— C2 Session ——
    def session_open(
        self,
        adapter_id: str,
        inputs: dict[str, Any] | None = None,
        open_callable: Callable[[dict[str, Any]], str] | None = None,
    ) -> AdapterInvocation:
        """C2 开启会话。"""
        self._check_adapter(adapter_id, "C2")
        inputs = inputs or {}
        session_id = open_callable(inputs) if open_callable else _uid("sess")
        inv = AdapterInvocation(
            adapter_id=adapter_id,
            capability_class="C2",
            operation="session.open",
            inputs=inputs,
            session_id=session_id,
            status="running",
        )
        self._add_invocation(inv)
        return inv

    def session_close(self, adapter_id: str, session_id: str) -> AdapterInvocation:
        """C2 关闭会话。"""
        self._check_adapter(adapter_id, "C2")
        inv = AdapterInvocation(
            adapter_id=adapter_id,
            capability_class="C2",
            operation="session.close",
            session_id=session_id,
            status="completed",
            ended_at=_now_ts(),
        )
        self._add_invocation(inv)
        return inv

    # —— 调用记录查询 ——
    def list_invocations(
        self,
        adapter_id: str | None = None,
        job_id: str | None = None,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[AdapterInvocation]:
        with self._lock:
            items = [self._invocations[i] for i in self._inv_order]
        if adapter_id:
            items = [i for i in items if i.adapter_id == adapter_id]
        if job_id:
            items = [i for i in items if i.job_id == job_id]
        if session_id:
            items = [i for i in items if i.session_id == session_id]
        items = sorted(items, key=lambda r: r.started_at, reverse=True)
        return items[:limit]


# ────────────────────────────────────────────────────────────────
# 单例
# ────────────────────────────────────────────────────────────────

_decision_lineage_engine: DecisionLineageEngine | None = None
_decision_lineage_lock = threading.Lock()


def get_decision_lineage_engine() -> DecisionLineageEngine:
    """获取 DecisionLineageEngine 单例（双重检查锁）。"""
    global _decision_lineage_engine
    if _decision_lineage_engine is None:
        with _decision_lineage_lock:
            if _decision_lineage_engine is None:
                _decision_lineage_engine = DecisionLineageEngine()
    return _decision_lineage_engine


_insight_backfill_engine: InsightBackfillEngine | None = None
_insight_backfill_lock = threading.Lock()


def get_insight_backfill_engine() -> InsightBackfillEngine:
    """获取 InsightBackfillEngine 单例（双重检查锁）。"""
    global _insight_backfill_engine
    if _insight_backfill_engine is None:
        with _insight_backfill_lock:
            if _insight_backfill_engine is None:
                _insight_backfill_engine = InsightBackfillEngine()
    return _insight_backfill_engine


_capability_adapter_engine: CapabilityAdapterEngine | None = None
_capability_adapter_lock = threading.Lock()


def get_capability_adapter_engine() -> CapabilityAdapterEngine:
    """获取 CapabilityAdapterEngine 单例（双重检查锁）。"""
    global _capability_adapter_engine
    if _capability_adapter_engine is None:
        with _capability_adapter_lock:
            if _capability_adapter_engine is None:
                _capability_adapter_engine = CapabilityAdapterEngine()
    return _capability_adapter_engine
