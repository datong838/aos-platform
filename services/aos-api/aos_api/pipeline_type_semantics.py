"""W2-Z · Pipeline 类型语义组：#94 Pipeline Types + #95 Incremental + #96 Streaming.

本模块收口 Pipeline 三种类型区分与增量/流式处理语义：
    - PipelineTypeEngine        Batch/Incremental/Streaming 三类型 + 处理语义（触发/状态机/容错）
    - IncrementalPipelineEngine watermark 水位线 + CDC 变更捕获 + checkpoint 检查点 + 增量执行
    - StreamingPipelineEngine   tumbling/sliding/session 三窗口 + watermark + 状态化操作

底层 PipelineEditor/PipelineOutputEngine/ExpectationEngine 不重写，仅作类型语义层。
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


# ────────────────────────────────────────────────────────────────
# 公共工具
# ────────────────────────────────────────────────────────────────

def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _now_ts() -> float:
    return time.time()


class PipelineTypeError(Exception):
    """W2-Z Pipeline 类型语义组错误。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


# ════════════════════════════════════════════════════════════════
# #94 Pipeline Types
# ════════════════════════════════════════════════════════════════

_VALID_PIPELINE_TYPES = {"batch", "incremental", "streaming"}
_VALID_TRIGGER_SEMANTICS = {"scheduled", "on_change", "continuous"}
_VALID_FAULT_STRATEGIES = {"restart", "skip", "checkpoint_replay"}


class PipelineTypeSpec(BaseModel):
    """管道类型定义。"""

    type: str                            # batch / incremental / streaming
    name: str
    description: str = ""
    trigger_semantics: str               # scheduled / on_change / continuous
    state_machine: list[str] = Field(default_factory=list)
    fault_strategy: str                  # restart / skip / checkpoint_replay
    default_write_mode: str = "append"
    supports_checkpoint: bool = False
    supports_windowing: bool = False
    enabled: bool = True


DEFAULT_PIPELINE_TYPES: list[PipelineTypeSpec] = [
    PipelineTypeSpec(
        type="batch",
        name="批处理管道",
        description="定时调度、全量处理、失败重启",
        trigger_semantics="scheduled",
        state_machine=["pending", "running", "succeeded", "failed"],
        fault_strategy="restart",
        default_write_mode="append",
        supports_checkpoint=False,
        supports_windowing=False,
    ),
    PipelineTypeSpec(
        type="incremental",
        name="增量管道",
        description="变更触发、水位线推进、断点续传",
        trigger_semantics="on_change",
        state_machine=["pending", "running", "succeeded", "failed"],
        fault_strategy="checkpoint_replay",
        default_write_mode="upsert",
        supports_checkpoint=True,
        supports_windowing=False,
    ),
    PipelineTypeSpec(
        type="streaming",
        name="流式管道",
        description="连续摄入、窗口聚合、水位线发射",
        trigger_semantics="continuous",
        state_machine=["running", "succeeded", "failed"],
        fault_strategy="skip",
        default_write_mode="append",
        supports_checkpoint=True,
        supports_windowing=True,
    ),
]


class PipelineTypeEngine:
    """#94 · Pipeline 类型引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._specs: dict[str, PipelineTypeSpec] = {}
        for spec in DEFAULT_PIPELINE_TYPES:
            self._specs[spec.type] = spec.model_copy()

    def register(self, spec: PipelineTypeSpec) -> PipelineTypeSpec:
        if spec.type not in _VALID_PIPELINE_TYPES:
            raise PipelineTypeError("INVALID_TYPE", f"未知管道类型：{spec.type}")
        if spec.trigger_semantics not in _VALID_TRIGGER_SEMANTICS:
            raise PipelineTypeError(
                "INVALID_TRIGGER", f"未知触发语义：{spec.trigger_semantics}",
            )
        if spec.fault_strategy not in _VALID_FAULT_STRATEGIES:
            raise PipelineTypeError(
                "INVALID_FAULT_STRATEGY", f"未知容错策略：{spec.fault_strategy}",
            )
        if not spec.name:
            raise PipelineTypeError("MISSING_NAME", "管道类型名称不能为空")
        with self._lock:
            self._specs[spec.type] = spec.model_copy()
            return spec.model_copy()

    def get(self, ptype: str) -> PipelineTypeSpec:
        with self._lock:
            s = self._specs.get(ptype)
        if not s:
            raise PipelineTypeError("NOT_FOUND", f"管道类型 {ptype} 未注册")
        return s.model_copy()

    def list(self, enabled_only: bool = False) -> list[PipelineTypeSpec]:
        with self._lock:
            items = list(self._specs.values())
        if enabled_only:
            items = [s for s in items if s.enabled]
        return [s.model_copy() for s in items]

    def update(self, ptype: str, updates: dict[str, Any]) -> PipelineTypeSpec:
        if "type" in updates:
            raise PipelineTypeError("IMMUTABLE_FIELD", "type 字段不可修改")
        with self._lock:
            s = self._specs.get(ptype)
            if not s:
                raise PipelineTypeError("NOT_FOUND", f"管道类型 {ptype} 未注册")
            if "trigger_semantics" in updates and updates["trigger_semantics"] not in _VALID_TRIGGER_SEMANTICS:
                raise PipelineTypeError(
                    "INVALID_TRIGGER", f"未知触发语义：{updates['trigger_semantics']}",
                )
            if "fault_strategy" in updates and updates["fault_strategy"] not in _VALID_FAULT_STRATEGIES:
                raise PipelineTypeError(
                    "INVALID_FAULT_STRATEGY", f"未知容错策略：{updates['fault_strategy']}",
                )
            new_s = s.model_copy(update=updates)
            self._specs[ptype] = new_s
            return new_s.model_copy()

    def delete(self, ptype: str) -> bool:
        with self._lock:
            if ptype not in self._specs:
                raise PipelineTypeError("NOT_FOUND", f"管道类型 {ptype} 未注册")
            del self._specs[ptype]
            return True

    def validate_run(self, ptype: str, write_mode: str) -> dict[str, Any]:
        spec = self.get(ptype)
        ok = (write_mode == spec.default_write_mode)
        hint = "" if ok else (
            f"类型 {ptype} 默认 write_mode={spec.default_write_mode}，"
            f"传入 write_mode={write_mode} 不匹配"
        )
        return {
            "type": ptype,
            "write_mode": write_mode,
            "ok": ok,
            "hint": hint,
            "trigger_semantics": spec.trigger_semantics,
            "fault_strategy": spec.fault_strategy,
        }


# ════════════════════════════════════════════════════════════════
# #95 Incremental Pipeline
# ════════════════════════════════════════════════════════════════

_VALID_OPERATIONS = {"insert", "update", "delete"}
_MAX_CHANGES = 200
_MAX_CHECKPOINTS = 200


class Watermark(BaseModel):
    """水位线。"""

    pipeline_id: str
    field: str
    value: str = ""
    updated_at: float = 0.0


class Checkpoint(BaseModel):
    """增量检查点。"""

    id: str = Field(default_factory=lambda: _uid("ckpt"))
    pipeline_id: str
    sequence: int = 0
    watermark_value: str = ""
    rows_processed: int = 0
    status: str = "pending"            # pending / committed / failed
    created_at: float = Field(default_factory=_now_ts)
    committed_at: float = 0.0


class ChangeRecord(BaseModel):
    """变更捕获记录。"""

    id: str = Field(default_factory=lambda: _uid("chg"))
    pipeline_id: str
    operation: str                     # insert / update / delete
    pk: str
    payload: dict[str, Any] = Field(default_factory=dict)
    watermark_value: str = ""
    captured_at: float = Field(default_factory=_now_ts)


class IncrementalRunResult(BaseModel):
    """增量运行结果。"""

    run_id: str = Field(default_factory=lambda: _uid("run"))
    pipeline_id: str
    changes: list[ChangeRecord] = Field(default_factory=list)
    rows_processed: int = 0
    new_watermark: str = ""
    checkpoint_id: str = ""
    status: str = "completed"          # completed / skipped / failed


class IncrementalPipelineEngine:
    """#95 · 增量管道引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._watermarks: dict[str, Watermark] = {}
        self._changes: list[ChangeRecord] = []
        self._checkpoints: list[Checkpoint] = []
        self._seq: dict[str, int] = {}

    def get_watermark(self, pipeline_id: str) -> Watermark:
        with self._lock:
            wm = self._watermarks.get(pipeline_id)
        if not wm:
            return Watermark(pipeline_id=pipeline_id, field="updated_at", value="")
        return wm.model_copy()

    def set_watermark(
        self, pipeline_id: str, field: str, value: str,
    ) -> Watermark:
        if not pipeline_id:
            raise PipelineTypeError("INVALID_PIPELINE_ID", "pipeline_id 不能为空")
        if not field:
            raise PipelineTypeError("INVALID_FIELD", "watermark field 不能为空")
        with self._lock:
            wm = Watermark(
                pipeline_id=pipeline_id, field=field, value=value,
                updated_at=_now_ts(),
            )
            self._watermarks[pipeline_id] = wm
            return wm.model_copy()

    def register_change(self, rec: ChangeRecord) -> ChangeRecord:
        if rec.operation not in _VALID_OPERATIONS:
            raise PipelineTypeError(
                "INVALID_OPERATION", f"未知变更操作：{rec.operation}",
            )
        if not rec.pipeline_id:
            raise PipelineTypeError("INVALID_PIPELINE_ID", "pipeline_id 不能为空")
        if not rec.pk:
            raise PipelineTypeError("INVALID_PK", "pk 不能为空")
        with self._lock:
            self._changes.append(rec)
            if len(self._changes) > _MAX_CHANGES:
                self._changes = self._changes[-_MAX_CHANGES:]
            return rec.model_copy()

    def list_changes(
        self, pipeline_id: str, op: str | None = None,
        since_watermark: str | None = None, limit: int = 50,
    ) -> list[ChangeRecord]:
        with self._lock:
            items = [c for c in self._changes if c.pipeline_id == pipeline_id]
        if op:
            items = [c for c in items if c.operation == op]
        if since_watermark:
            items = [c for c in items if c.watermark_value > since_watermark]
        return [c.model_copy() for c in items[-limit:]]

    def create_checkpoint(self, pipeline_id: str) -> Checkpoint:
        if not pipeline_id:
            raise PipelineTypeError("INVALID_PIPELINE_ID", "pipeline_id 不能为空")
        with self._lock:
            seq = self._seq.get(pipeline_id, 0) + 1
            self._seq[pipeline_id] = seq
            ckpt = Checkpoint(
                pipeline_id=pipeline_id, sequence=seq,
                watermark_value=self._watermarks.get(pipeline_id, Watermark(
                    pipeline_id=pipeline_id, field="updated_at")).value,
            )
            self._checkpoints.append(ckpt)
            if len(self._checkpoints) > _MAX_CHECKPOINTS:
                self._checkpoints = self._checkpoints[-_MAX_CHECKPOINTS:]
            return ckpt.model_copy()

    def commit_checkpoint(self, checkpoint_id: str) -> Checkpoint:
        with self._lock:
            for ckpt in self._checkpoints:
                if ckpt.id == checkpoint_id:
                    if ckpt.status == "committed":
                        raise PipelineTypeError(
                            "ALREADY_COMMITTED", f"检查点 {checkpoint_id} 已提交",
                        )
                    ckpt.status = "committed"
                    ckpt.committed_at = _now_ts()
                    return ckpt.model_copy()
        raise PipelineTypeError("NOT_FOUND", f"检查点 {checkpoint_id} 不存在")

    def list_checkpoints(self, pipeline_id: str) -> list[Checkpoint]:
        with self._lock:
            items = [c for c in self._checkpoints if c.pipeline_id == pipeline_id]
        return [c.model_copy() for c in items]

    def process_increment(
        self, pipeline_id: str,
        changes: list[ChangeRecord] | None = None,
    ) -> IncrementalRunResult:
        if not pipeline_id:
            raise PipelineTypeError("INVALID_PIPELINE_ID", "pipeline_id 不能为空")
        with self._lock:
            wm = self._watermarks.get(pipeline_id)
            current_wm = wm.value if wm else ""

        # 收集变更：传入优先，否则取 watermark 之后
        if changes is not None:
            pending = changes
        else:
            pending = self.list_changes(
                pipeline_id, since_watermark=current_wm if current_wm else None,
            )

        if not pending:
            return IncrementalRunResult(
                pipeline_id=pipeline_id, changes=[], rows_processed=0,
                new_watermark=current_wm, checkpoint_id="",
                status="skipped",
            )

        # 创建 checkpoint(pending)
        ckpt = self.create_checkpoint(pipeline_id)
        ckpt.rows_processed = len(pending)
        # 推进 watermark 到最新变更
        new_wm = max(
            (c.watermark_value for c in pending if c.watermark_value),
            default=current_wm,
        )
        if new_wm and new_wm > current_wm:
            wm_field = wm.field if wm else "updated_at"
            self.set_watermark(pipeline_id, wm_field, new_wm)
        # 提交 checkpoint
        self.commit_checkpoint(ckpt.id)

        return IncrementalRunResult(
            pipeline_id=pipeline_id,
            changes=[c.model_copy() for c in pending],
            rows_processed=len(pending),
            new_watermark=new_wm or current_wm,
            checkpoint_id=ckpt.id,
            status="completed",
        )


# ════════════════════════════════════════════════════════════════
# #96 Streaming Pipeline
# ════════════════════════════════════════════════════════════════

_VALID_WINDOW_TYPES = {"tumbling", "sliding", "session"}
_MAX_EVENTS = 200
_MAX_WINDOWS = 200


class WindowSpec(BaseModel):
    """窗口规格。"""

    type: str                          # tumbling / sliding / session
    size_ms: int = 0
    slide_ms: int = 0
    gap_ms: int = 0
    watermark_field: str = "event_ts"


class StreamEvent(BaseModel):
    """流事件。"""

    id: str = Field(default_factory=lambda: _uid("evt"))
    pipeline_id: str
    key: str
    event_ts: float = 0.0
    payload: dict[str, Any] = Field(default_factory=dict)
    processed: bool = False


class WindowState(BaseModel):
    """窗口状态。"""

    window_id: str = Field(default_factory=lambda: _uid("win"))
    pipeline_id: str
    spec: WindowSpec
    start_ts: float = 0.0
    end_ts: float = 0.0
    events: list[StreamEvent] = Field(default_factory=list)
    open: bool = True
    emitted: bool = False


class StreamProcessResult(BaseModel):
    """流处理结果。"""

    pipeline_id: str
    processed: int = 0
    windows_opened: int = 0
    windows_closed: int = 0
    watermark_advanced: float = 0.0


class StreamingPipelineEngine:
    """#96 · 流式管道引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._window_specs: dict[str, WindowSpec] = {}
        self._events: list[StreamEvent] = []
        self._windows: list[WindowState] = []
        self._watermarks: dict[str, float] = {}

    def register_window(
        self, pipeline_id: str, spec: WindowSpec,
    ) -> WindowSpec:
        if spec.type not in _VALID_WINDOW_TYPES:
            raise PipelineTypeError(
                "INVALID_WINDOW_TYPE", f"未知窗口类型：{spec.type}",
            )
        if not pipeline_id:
            raise PipelineTypeError("INVALID_PIPELINE_ID", "pipeline_id 不能为空")
        if spec.type == "tumbling" and spec.size_ms <= 0:
            raise PipelineTypeError(
                "INVALID_SIZE", "tumbling 窗口 size_ms 必须 > 0",
            )
        if spec.type == "sliding" and (spec.size_ms <= 0 or spec.slide_ms <= 0):
            raise PipelineTypeError(
                "INVALID_SIZE", "sliding 窗口 size_ms 和 slide_ms 必须 > 0",
            )
        if spec.type == "session" and spec.gap_ms <= 0:
            raise PipelineTypeError(
                "INVALID_GAP", "session 窗口 gap_ms 必须 > 0",
            )
        with self._lock:
            self._window_specs[pipeline_id] = spec.model_copy()
            return spec.model_copy()

    def get_window(self, pipeline_id: str) -> WindowSpec:
        with self._lock:
            spec = self._window_specs.get(pipeline_id)
        if not spec:
            raise PipelineTypeError(
                "NOT_FOUND", f"管道 {pipeline_id} 未注册窗口规格",
            )
        return spec.model_copy()

    def ingest(self, event: StreamEvent) -> StreamEvent:
        if not event.pipeline_id:
            raise PipelineTypeError("INVALID_PIPELINE_ID", "pipeline_id 不能为空")
        with self._lock:
            spec = self._window_specs.get(event.pipeline_id)
            if not spec:
                raise PipelineTypeError(
                    "NOT_FOUND",
                    f"管道 {event.pipeline_id} 未注册窗口规格",
                )
            assigned = self._assign_windows_locked(event, spec)
            event.processed = True
            self._events.append(event)
            if len(self._events) > _MAX_EVENTS:
                self._events = self._events[-_MAX_EVENTS:]
            for win in assigned:
                win.events.append(event.model_copy())
            return event.model_copy()

    def _assign_windows_locked(
        self, event: StreamEvent, spec: WindowSpec,
    ) -> list[WindowState]:
        """按窗口规格分配事件到窗口，返回被更新的窗口列表。"""
        ts_ms = event.event_ts
        assigned: list[WindowState] = []
        pid = event.pipeline_id

        if spec.type == "tumbling":
            size = spec.size_ms
            start = (int(ts_ms) // size) * size
            end = start + size
            win = self._find_or_create_tumbling_locked(pid, spec, start, end)
            if win.open:
                assigned.append(win)

        elif spec.type == "sliding":
            size = spec.size_ms
            slide = spec.slide_ms
            # 枚举所有覆盖 ts 的窗口起点：w <= ts < w+size
            # w = k*slide，k 从 floor((ts-size+slide)/slide) 到 floor(ts/slide)
            k_min = (int(ts_ms) - size + slide) // slide
            if k_min < 0:
                k_min = 0
            k_max = int(ts_ms) // slide
            for k in range(k_min, k_max + 1):
                start = k * slide
                end = start + size
                if start <= ts_ms < end:
                    win = self._find_or_create_tumbling_locked(pid, spec, start, end)
                    if win.open:
                        assigned.append(win)

        elif spec.type == "session":
            gap = spec.gap_ms
            # 按 key 找当前会话窗口；若 event_ts - last_ts <= gap 合并，否则新建
            existing = [
                w for w in self._windows
                if w.pipeline_id == pid and w.spec.type == "session"
                and w.open and any(
                    e.key == event.key for e in w.events
                )
            ]
            merged = False
            for win in existing:
                last_ts = max((e.event_ts for e in win.events), default=0.0)
                if ts_ms - last_ts <= gap:
                    if ts_ms > win.end_ts:
                        win.end_ts = ts_ms
                    assigned.append(win)
                    merged = True
                    break
            if not merged:
                new_win = WindowState(
                    pipeline_id=pid, spec=spec.model_copy(),
                    start_ts=ts_ms, end_ts=ts_ms,
                    events=[], open=True, emitted=False,
                )
                self._windows.append(new_win)
                if len(self._windows) > _MAX_WINDOWS:
                    self._windows = self._windows[-_MAX_WINDOWS:]
                assigned.append(new_win)

        return assigned

    def _find_or_create_tumbling_locked(
        self, pid: str, spec: WindowSpec, start: float, end: float,
    ) -> WindowState:
        for w in self._windows:
            if (
                w.pipeline_id == pid and w.start_ts == start
                and w.end_ts == end and w.spec.type == spec.type
            ):
                return w
        new_win = WindowState(
            pipeline_id=pid, spec=spec.model_copy(),
            start_ts=start, end_ts=end,
            events=[], open=True, emitted=False,
        )
        self._windows.append(new_win)
        if len(self._windows) > _MAX_WINDOWS:
            self._windows = self._windows[-_MAX_WINDOWS:]
        return new_win

    def list_events(
        self, pipeline_id: str, processed_only: bool = False, limit: int = 50,
    ) -> list[StreamEvent]:
        with self._lock:
            items = [e for e in self._events if e.pipeline_id == pipeline_id]
        if processed_only:
            items = [e for e in items if e.processed]
        return [e.model_copy() for e in items[-limit:]]

    def list_windows(
        self, pipeline_id: str, open_only: bool = False, limit: int = 50,
    ) -> list[WindowState]:
        with self._lock:
            items = [w for w in self._windows if w.pipeline_id == pipeline_id]
        if open_only:
            items = [w for w in items if w.open]
        return [w.model_copy() for w in items[-limit:]]

    def advance_watermark(
        self, pipeline_id: str, new_watermark: float,
    ) -> StreamProcessResult:
        if not pipeline_id:
            raise PipelineTypeError("INVALID_PIPELINE_ID", "pipeline_id 不能为空")
        with self._lock:
            old_wm = self._watermarks.get(pipeline_id, 0.0)
            if new_watermark < old_wm:
                raise PipelineTypeError(
                    "WATERMARK_REGRESS",
                    f"水位线不能回退：当前 {old_wm} > 新 {new_watermark}",
                )
            self._watermarks[pipeline_id] = new_watermark
            closed = 0
            for w in self._windows:
                if (
                    w.pipeline_id == pipeline_id and w.open
                    and w.end_ts <= new_watermark
                ):
                    w.open = False
                    w.emitted = True
                    closed += 1
            processed = sum(
                1 for e in self._events
                if e.pipeline_id == pipeline_id and e.event_ts <= new_watermark
            )
            return StreamProcessResult(
                pipeline_id=pipeline_id,
                processed=processed,
                windows_opened=0,
                windows_closed=closed,
                watermark_advanced=new_watermark,
            )

    def close_window(self, window_id: str) -> WindowState:
        with self._lock:
            for w in self._windows:
                if w.window_id == window_id:
                    w.open = False
                    w.emitted = True
                    return w.model_copy()
        raise PipelineTypeError("NOT_FOUND", f"窗口 {window_id} 不存在")


# ════════════════════════════════════════════════════════════════
# #97 Compute Profile（计算选项：Standard / Faster / External）
# ════════════════════════════════════════════════════════════════

_VALID_COMPUTE_PROFILES = {"standard", "faster", "external"}


class ComputeProfileSpec(BaseModel):
    """计算配置文件。"""

    profile: str                         # standard / faster / external
    description: str = ""
    driver_cores: float = 1.0
    driver_memory_mb: int = 2048
    executor_cores: float = 1.0
    executor_memory_mb: int = 4096
    executor_count: int = 2
    external_endpoint: str = ""          # external 模式的远端计算端点
    auto_scale: bool = False
    cost_weight: float = 1.0             # 成本权重（用于计费估算）
    enabled: bool = True


DEFAULT_COMPUTE_PROFILES: list[ComputeProfileSpec] = [
    ComputeProfileSpec(
        profile="standard",
        description="标准计算配置：均衡成本与性能",
        driver_cores=1.0, driver_memory_mb=2048,
        executor_cores=1.0, executor_memory_mb=4096,
        executor_count=2, auto_scale=False, cost_weight=1.0,
    ),
    ComputeProfileSpec(
        profile="faster",
        description="加速计算配置：更多资源、并行优化",
        driver_cores=2.0, driver_memory_mb=4096,
        executor_cores=2.0, executor_memory_mb=8192,
        executor_count=4, auto_scale=True, cost_weight=2.5,
    ),
    ComputeProfileSpec(
        profile="external",
        description="外部计算配置：委托远端计算引擎",
        driver_cores=0, driver_memory_mb=0,
        executor_cores=0, executor_memory_mb=0,
        executor_count=0,
        external_endpoint="https://compute.external.local",
        auto_scale=False, cost_weight=1.5,
    ),
]


class ComputeProfileEngine:
    """#97 · 计算选项引擎（Standard / Faster / External）。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._profiles: dict[str, ComputeProfileSpec] = {}
        self._assignments: dict[str, str] = {}   # pipeline_id -> profile
        for spec in DEFAULT_COMPUTE_PROFILES:
            self._profiles[spec.profile] = spec.model_copy()

    def register(self, spec: ComputeProfileSpec) -> ComputeProfileSpec:
        if spec.profile not in _VALID_COMPUTE_PROFILES:
            raise PipelineTypeError(
                "INVALID_PROFILE", f"未知计算选项：{spec.profile}",
            )
        if not spec.description:
            raise PipelineTypeError("MISSING_DESC", "描述不能为空")
        if spec.profile == "external" and not spec.external_endpoint:
            raise PipelineTypeError(
                "MISSING_ENDPOINT", "external 模式必须指定 external_endpoint",
            )
        with self._lock:
            self._profiles[spec.profile] = spec.model_copy()
            return spec.model_copy()

    def get(self, profile: str) -> ComputeProfileSpec:
        with self._lock:
            s = self._profiles.get(profile)
        if not s:
            raise PipelineTypeError("NOT_FOUND", f"计算选项 {profile} 未注册")
        return s.model_copy()

    def list(self, enabled_only: bool = False) -> list[ComputeProfileSpec]:
        with self._lock:
            items = list(self._profiles.values())
        if enabled_only:
            items = [s for s in items if s.enabled]
        return [s.model_copy() for s in items]

    def update(self, profile: str, updates: dict[str, Any]) -> ComputeProfileSpec:
        if "profile" in updates:
            raise PipelineTypeError("IMMUTABLE_FIELD", "profile 字段不可修改")
        with self._lock:
            s = self._profiles.get(profile)
            if not s:
                raise PipelineTypeError("NOT_FOUND", f"计算选项 {profile} 未注册")
            if "external_endpoint" in updates and updates["external_endpoint"]:
                if profile != "external":
                    raise PipelineTypeError(
                        "ENDPOINT_MISMATCH",
                        "只有 external 模式可设 external_endpoint",
                    )
            new_s = s.model_copy(update=updates)
            self._profiles[profile] = new_s
            return new_s.model_copy()

    def assign(self, pipeline_id: str, profile: str) -> dict[str, Any]:
        if profile not in _VALID_COMPUTE_PROFILES:
            raise PipelineTypeError(
                "INVALID_PROFILE", f"未知计算选项：{profile}",
            )
        if not pipeline_id:
            raise PipelineTypeError("INVALID_PIPELINE_ID", "pipeline_id 不能为空")
        with self._lock:
            self._assignments[pipeline_id] = profile
            spec = self._profiles.get(profile)
        return {
            "pipeline_id": pipeline_id,
            "profile": profile,
            "spec": spec.model_copy() if spec else None,
        }

    def get_assignment(self, pipeline_id: str) -> dict[str, Any]:
        with self._lock:
            profile = self._assignments.get(pipeline_id)
            spec = self._profiles.get(profile) if profile else None
        return {
            "pipeline_id": pipeline_id,
            "profile": profile,
            "spec": spec.model_copy() if spec else None,
        }

    def estimate_cost(
        self, profile: str, duration_minutes: float,
    ) -> dict[str, Any]:
        spec = self.get(profile)
        if spec.profile == "external":
            cost = duration_minutes * spec.cost_weight * 0.5
        else:
            total_cores = spec.driver_cores + spec.executor_cores * spec.executor_count
            total_mem_gb = (spec.driver_memory_mb + spec.executor_memory_mb * spec.executor_count) / 1024
            cost = duration_minutes * (total_cores * 0.08 + total_mem_gb * 0.02) * spec.cost_weight
        return {
            "profile": profile,
            "duration_minutes": duration_minutes,
            "estimated_cost": round(cost, 4),
            "currency": "CNY",
        }


# ════════════════════════════════════════════════════════════════
# #98 Streaming Performance & Fault Tolerance（流式性能 / 容错）
# ════════════════════════════════════════════════════════════════

_VALID_BACKPRESSURE = {"none", "buffer", "drop_oldest", "block"}
_VALID_FAULT_TOLERANCE = {"at_most_once", "at_least_once", "exactly_once"}


class BackpressurePolicy(BaseModel):
    """背压策略。"""

    strategy: str = "buffer"            # none / buffer / drop_oldest / block
    buffer_size: int = 10000
    high_watermark_pct: float = 80.0    # 触发背压阈值（缓冲区占用率）
    low_watermark_pct: float = 50.0     # 解除背压阈值
    drop_count: int = 0                 # 累计丢弃事件数（只读）


class ResourceLimit(BaseModel):
    """资源限制。"""

    max_in_flight: int = 1000           # 最大在途事件数
    max_parallelism: int = 4            # 最大并行度
    cpu_limit_cores: float = 2.0
    memory_limit_mb: int = 4096
    network_bandwidth_mbps: int = 0     # 0 = 不限


class FaultToleranceSpec(BaseModel):
    """容错配置。"""

    level: str = "at_least_once"        # at_most_once / at_least_once / exactly_once
    checkpoint_interval_ms: int = 30000
    max_retries: int = 3
    retry_backoff_ms: int = 1000
    dead_letter_queue: bool = True
    auto_restart: bool = True
    restart_delay_ms: int = 5000


class StreamingPerfConfig(BaseModel):
    """流式性能综合配置。"""

    pipeline_id: str
    backpressure: BackpressurePolicy = Field(default_factory=BackpressurePolicy)
    resource: ResourceLimit = Field(default_factory=ResourceLimit)
    fault: FaultToleranceSpec = Field(default_factory=FaultToleranceSpec)
    enabled: bool = True


class StreamingPerfEngine:
    """#98 · 流式性能 / 背压 / 资源管理 / 容错引擎。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._configs: dict[str, StreamingPerfConfig] = {}
        self._dlq: list[dict[str, Any]] = []       # dead letter queue
        self._current_load: dict[str, int] = {}    # pipeline_id -> 在途事件数

    def set_config(self, cfg: StreamingPerfConfig) -> StreamingPerfConfig:
        if cfg.backpressure.strategy not in _VALID_BACKPRESSURE:
            raise PipelineTypeError(
                "INVALID_BACKPRESSURE", f"未知背压策略：{cfg.backpressure.strategy}",
            )
        if cfg.fault.level not in _VALID_FAULT_TOLERANCE:
            raise PipelineTypeError(
                "INVALID_FAULT_LEVEL", f"未知容错级别：{cfg.fault.level}",
            )
        if not cfg.pipeline_id:
            raise PipelineTypeError("INVALID_PIPELINE_ID", "pipeline_id 不能为空")
        if cfg.resource.max_parallelism < 1:
            raise PipelineTypeError(
                "INVALID_PARALLELISM", "max_parallelism 必须 >= 1",
            )
        with self._lock:
            self._configs[cfg.pipeline_id] = cfg.model_copy()
            return cfg.model_copy()

    def get_config(self, pipeline_id: str) -> StreamingPerfConfig:
        with self._lock:
            cfg = self._configs.get(pipeline_id)
        if not cfg:
            # 返回默认配置
            return StreamingPerfConfig(pipeline_id=pipeline_id)
        return cfg.model_copy()

    def check_backpressure(
        self, pipeline_id: str, current_buffer_usage: int,
    ) -> dict[str, Any]:
        cfg = self.get_config(pipeline_id)
        bp = cfg.backpressure
        capacity = bp.buffer_size
        usage_pct = (current_buffer_usage / capacity * 100) if capacity > 0 else 0

        action = "normal"
        if usage_pct >= bp.high_watermark_pct:
            if bp.strategy == "drop_oldest":
                action = "drop"
            elif bp.strategy == "block":
                action = "block"
            elif bp.strategy == "buffer":
                action = "warn"
            elif bp.strategy == "none":
                action = "ignore"
        elif usage_pct <= bp.low_watermark_pct:
            action = "normal"

        return {
            "pipeline_id": pipeline_id,
            "strategy": bp.strategy,
            "buffer_usage": current_buffer_usage,
            "buffer_capacity": capacity,
            "usage_pct": round(usage_pct, 2),
            "high_watermark_pct": bp.high_watermark_pct,
            "low_watermark_pct": bp.low_watermark_pct,
            "action": action,
            "should_throttle": action in ("drop", "block", "warn"),
        }

    def record_load(self, pipeline_id: str, delta: int) -> dict[str, Any]:
        with self._lock:
            current = self._current_load.get(pipeline_id, 0)
            new_val = max(0, current + delta)
            self._current_load[pipeline_id] = new_val
            cfg = self._configs.get(pipeline_id)
        limit = cfg.resource.max_in_flight if cfg else 1000
        return {
            "pipeline_id": pipeline_id,
            "in_flight": new_val,
            "max_in_flight": limit,
            "overloaded": new_val >= limit,
        }

    def send_to_dlq(
        self, pipeline_id: str, event: dict[str, Any], reason: str,
    ) -> dict[str, Any]:
        with self._lock:
            entry = {
                "id": _uid("dlq"),
                "pipeline_id": pipeline_id,
                "event": event,
                "reason": reason,
                "sent_at": _now_ts(),
            }
            self._dlq.append(entry)
            if len(self._dlq) > 500:
                self._dlq = self._dlq[-500:]
            return entry

    def list_dlq(
        self, pipeline_id: str | None = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        with self._lock:
            items = list(self._dlq)
        if pipeline_id:
            items = [d for d in items if d["pipeline_id"] == pipeline_id]
        return items[-limit:]

    def get_health(self, pipeline_id: str) -> dict[str, Any]:
        cfg = self.get_config(pipeline_id)
        with self._lock:
            in_flight = self._current_load.get(pipeline_id, 0)
            dlq_count = sum(1 for d in self._dlq if d["pipeline_id"] == pipeline_id)
        load_pct = (in_flight / cfg.resource.max_in_flight * 100) if cfg.resource.max_in_flight > 0 else 0
        return {
            "pipeline_id": pipeline_id,
            "in_flight": in_flight,
            "max_in_flight": cfg.resource.max_in_flight,
            "load_pct": round(load_pct, 2),
            "dlq_count": dlq_count,
            "fault_level": cfg.fault.level,
            "auto_restart": cfg.fault.auto_restart,
            "status": "healthy" if load_pct < 80 else "stressed" if load_pct < 100 else "overloaded",
        }


# ════════════════════════════════════════════════════════════════
# 单例
# ════════════════════════════════════════════════════════════════

_pipeline_type_engine: PipelineTypeEngine | None = None
_pipeline_type_lock = threading.Lock()

_incremental_engine: IncrementalPipelineEngine | None = None
_incremental_lock = threading.Lock()

_streaming_engine: StreamingPipelineEngine | None = None
_streaming_lock = threading.Lock()

_compute_profile_engine: ComputeProfileEngine | None = None
_compute_profile_lock = threading.Lock()

_streaming_perf_engine: StreamingPerfEngine | None = None
_streaming_perf_lock = threading.Lock()


def get_pipeline_type_engine() -> PipelineTypeEngine:
    global _pipeline_type_engine
    if _pipeline_type_engine is None:
        with _pipeline_type_lock:
            if _pipeline_type_engine is None:
                _pipeline_type_engine = PipelineTypeEngine()
    return _pipeline_type_engine


def get_incremental_engine() -> IncrementalPipelineEngine:
    global _incremental_engine
    if _incremental_engine is None:
        with _incremental_lock:
            if _incremental_engine is None:
                _incremental_engine = IncrementalPipelineEngine()
    return _incremental_engine


def get_streaming_engine() -> StreamingPipelineEngine:
    global _streaming_engine
    if _streaming_engine is None:
        with _streaming_lock:
            if _streaming_engine is None:
                _streaming_engine = StreamingPipelineEngine()
    return _streaming_engine


def get_compute_profile_engine() -> ComputeProfileEngine:
    global _compute_profile_engine
    if _compute_profile_engine is None:
        with _compute_profile_lock:
            if _compute_profile_engine is None:
                _compute_profile_engine = ComputeProfileEngine()
    return _compute_profile_engine


def get_streaming_perf_engine() -> StreamingPerfEngine:
    global _streaming_perf_engine
    if _streaming_perf_engine is None:
        with _streaming_perf_lock:
            if _streaming_perf_engine is None:
                _streaming_perf_engine = StreamingPerfEngine()
    return _streaming_perf_engine
