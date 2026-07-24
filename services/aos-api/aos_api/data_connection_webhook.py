"""W2-AJ · Data Connection 流导出与 Webhook 组（#122 #123 #124）.

- StreamExportEngine：Stream → Kafka/Kinesis/PubSub 导出
- WebhookPipelineEngine：多步 Webhook 调用编排
- WebhookOutputEngine：响应字段提取与类型转换
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from threading import Lock
from typing import Optional

from pydantic import BaseModel, Field

_MAX_STREAM_EXPORTS = 200
_MAX_EVENTS_PER_TASK = 200
_MAX_PIPELINES = 200
_MAX_RUNS_PER_PIPELINE = 200
_MAX_OUTPUT_CONFIGS = 200


# ════════════════════ 错误 ════════════════════

class DataConnectionWebhookError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


# ════════════════════ #122 Stream Export ════════════════════

_VALID_STREAM_TARGETS = {"kafka", "kinesis", "pubsub"}
_VALID_PARTITION_STRATEGIES = {"round_robin", "key_hash", "random"}
_VALID_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
_VALID_WEBHOOK_AUTH_TYPES = {"none", "bearer", "basic", "api_key", "hmac"}
_VALID_TARGET_TYPES = {"string", "integer", "float", "boolean", "json"}


class StreamExportTask(BaseModel):
    id: str = ""
    name: str
    source_stream: str = ""
    target_type: str = "kafka"
    target_config: dict = Field(default_factory=dict)
    partition_strategy: str = "round_robin"
    key_field: str = ""
    batch_size: int = 100
    enabled: bool = True
    status: str = "stopped"
    total_events: int = 0
    last_event_at: float = 0.0
    error_message: str = ""
    created_at: float = 0.0


class StreamExportEvent(BaseModel):
    event_id: str = ""
    task_id: str
    payload: dict = Field(default_factory=dict)
    key: str = ""
    partition: int = 0
    status: str = "pending"
    sent_at: float = 0.0
    error_message: str = ""


class StreamExportEngine:
    def __init__(self) -> None:
        self._tasks: dict[str, StreamExportTask] = {}
        self._events: dict[str, deque[StreamExportEvent]] = {}
        self._partition_counters: dict[str, int] = {}
        self._lock = Lock()

    def register(self, task: StreamExportTask) -> StreamExportTask:
        if not task.name:
            raise DataConnectionWebhookError("MISSING_NAME", "name is required")
        if not task.source_stream:
            raise DataConnectionWebhookError(
                "MISSING_SOURCE_STREAM", "source_stream is required"
            )
        if task.target_type not in _VALID_STREAM_TARGETS:
            raise DataConnectionWebhookError(
                "INVALID_TARGET_TYPE",
                f"target_type must be one of {_VALID_STREAM_TARGETS}",
            )
        if task.partition_strategy not in _VALID_PARTITION_STRATEGIES:
            raise DataConnectionWebhookError(
                "INVALID_PARTITION_STRATEGY",
                f"partition_strategy must be one of {_VALID_PARTITION_STRATEGIES}",
            )
        if task.batch_size <= 0:
            raise DataConnectionWebhookError(
                "INVALID_BATCH_SIZE", "batch_size must be > 0"
            )
        with self._lock:
            task.id = f"sex-{uuid.uuid4().hex[:8]}"
            task.created_at = time.time()
            self._tasks[task.id] = task
            self._events[task.id] = deque(maxlen=_MAX_EVENTS_PER_TASK)
            self._partition_counters[task.id] = 0
            if len(self._tasks) > _MAX_STREAM_EXPORTS:
                oldest = min(self._tasks.values(), key=lambda t: t.created_at)
                self._tasks.pop(oldest.id, None)
                self._events.pop(oldest.id, None)
                self._partition_counters.pop(oldest.id, None)
            return task.model_copy(deep=True)

    def get(self, task_id: str) -> StreamExportTask:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionWebhookError("NOT_FOUND", f"task {task_id} not found")
            return t.model_copy(deep=True)

    def list(
        self,
        source_stream: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[StreamExportTask]:
        with self._lock:
            result = list(self._tasks.values())
            if source_stream:
                result = [t for t in result if t.source_stream == source_stream]
            if status:
                result = [t for t in result if t.status == status]
            return [t.model_copy(deep=True) for t in result]

    def update(self, task_id: str, updates: dict) -> StreamExportTask:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionWebhookError("NOT_FOUND", f"task {task_id} not found")
            data = t.model_dump()
            data.update({k: v for k, v in updates.items() if k in {
                "name", "source_stream", "target_type", "target_config",
                "partition_strategy", "key_field", "batch_size", "enabled",
            }})
            if not data["name"]:
                raise DataConnectionWebhookError("MISSING_NAME", "name is required")
            if not data["source_stream"]:
                raise DataConnectionWebhookError(
                    "MISSING_SOURCE_STREAM", "source_stream is required"
                )
            if data["target_type"] not in _VALID_STREAM_TARGETS:
                raise DataConnectionWebhookError(
                    "INVALID_TARGET_TYPE",
                    f"target_type must be one of {_VALID_STREAM_TARGETS}",
                )
            if data["partition_strategy"] not in _VALID_PARTITION_STRATEGIES:
                raise DataConnectionWebhookError(
                    "INVALID_PARTITION_STRATEGY",
                    f"partition_strategy must be one of {_VALID_PARTITION_STRATEGIES}",
                )
            if data["batch_size"] <= 0:
                raise DataConnectionWebhookError(
                    "INVALID_BATCH_SIZE", "batch_size must be > 0"
                )
            updated = StreamExportTask(**data)
            self._tasks[task_id] = updated
            return updated.model_copy(deep=True)

    def delete(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                self._events.pop(task_id, None)
                self._partition_counters.pop(task_id, None)
                return True
            return False

    def start(self, task_id: str) -> StreamExportTask:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionWebhookError("NOT_FOUND", f"task {task_id} not found")
            if t.status != "stopped":
                raise DataConnectionWebhookError(
                    "TASK_NOT_STOPPED", "only stopped tasks can be started"
                )
            if not t.enabled:
                raise DataConnectionWebhookError(
                    "TASK_DISABLED", "task is disabled"
                )
            t.status = "running"
            return t.model_copy(deep=True)

    def stop(self, task_id: str) -> StreamExportTask:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionWebhookError("NOT_FOUND", f"task {task_id} not found")
            if t.status != "running":
                raise DataConnectionWebhookError(
                    "TASK_NOT_RUNNING", "only running tasks can be stopped"
                )
            t.status = "stopped"
            return t.model_copy(deep=True)

    def _compute_partition(self, task: StreamExportTask, key: str, num_partitions: int = 4) -> int:
        if task.partition_strategy == "round_robin":
            counter = self._partition_counters.get(task.id, 0)
            partition = counter % num_partitions
            self._partition_counters[task.id] = counter + 1
            return partition
        if task.partition_strategy == "key_hash":
            return hash(key) % num_partitions if key else 0
        import random
        return random.randint(0, num_partitions - 1)

    def publish_event(
        self,
        task_id: str,
        payload: dict,
        key: str = "",
    ) -> StreamExportEvent:
        with self._lock:
            t = self._tasks.get(task_id)
            if not t:
                raise DataConnectionWebhookError("NOT_FOUND", f"task {task_id} not found")
            if t.status != "running":
                raise DataConnectionWebhookError(
                    "TASK_NOT_RUNNING", "only running tasks can publish"
                )
            if not key and t.key_field:
                key = str(payload.get(t.key_field, ""))
            partition = self._compute_partition(t, key)
            event = StreamExportEvent(
                event_id=f"sev-{uuid.uuid4().hex[:8]}",
                task_id=task_id,
                payload=payload,
                key=key,
                partition=partition,
                status="sent",
                sent_at=time.time(),
            )
            self._events[task_id].append(event)
            t.total_events += 1
            t.last_event_at = event.sent_at
            return event.model_copy(deep=True)

    def publish_batch(
        self,
        task_id: str,
        events: list[dict],
    ) -> list[StreamExportEvent]:
        results = []
        for ev in events:
            payload = ev.get("payload", ev)
            key = ev.get("key", "") if isinstance(ev, dict) else ""
            results.append(self.publish_event(task_id, payload, key))
        return results

    def list_events(
        self,
        task_id: str,
        limit: int = 50,
    ) -> list[StreamExportEvent]:
        with self._lock:
            if task_id not in self._tasks:
                raise DataConnectionWebhookError("NOT_FOUND", f"task {task_id} not found")
            evs = list(self._events.get(task_id, []))
            evs.sort(key=lambda e: e.sent_at, reverse=True)
            return [e.model_copy(deep=True) for e in evs[:limit]]


_stream_export_engine: Optional[StreamExportEngine] = None
_stream_export_lock = Lock()


def get_stream_export_engine() -> StreamExportEngine:
    global _stream_export_engine
    if _stream_export_engine is None:
        with _stream_export_lock:
            if _stream_export_engine is None:
                _stream_export_engine = StreamExportEngine()
    return _stream_export_engine


# ════════════════════ #123 Webhook Pipeline ════════════════════

class WebhookPipelineStep(BaseModel):
    step_id: str = ""
    name: str = ""
    url: str = ""
    method: str = "POST"
    auth_type: str = "none"
    auth_config: dict = Field(default_factory=dict)
    request_template: dict = Field(default_factory=dict)
    headers: dict = Field(default_factory=dict)
    timeout_ms: int = 30000
    retry_count: int = 0
    condition: str = ""
    output_mapping: dict = Field(default_factory=dict)


class WebhookPipeline(BaseModel):
    id: str = ""
    name: str
    description: str = ""
    steps: list[WebhookPipelineStep] = Field(default_factory=list)
    status: str = "draft"
    created_at: float = 0.0
    total_runs: int = 0


class PipelineRun(BaseModel):
    run_id: str = ""
    pipeline_id: str
    status: str = "running"
    started_at: float = 0.0
    completed_at: float = 0.0
    current_step: int = 0
    step_results: list[dict] = Field(default_factory=list)
    error_message: str = ""
    outputs: dict = Field(default_factory=dict)
    initial_input: dict = Field(default_factory=dict)


def _resolve_template(template: object, context: dict) -> object:
    """递归解析 {{path.to.value}} 模板引用。"""
    import re
    if isinstance(template, str):
        def replace(match: re.Match) -> str:
            path = match.group(1)
            keys = path.split(".")
            val: object = context
            for k in keys:
                if isinstance(val, dict) and k in val:
                    val = val[k]
                else:
                    return match.group(0)
            return str(val) if not isinstance(val, (dict, list)) else str(val)
        return re.sub(r"\{\{([^}]+)\}\}", replace, template)
    if isinstance(template, dict):
        return {k: _resolve_template(v, context) for k, v in template.items()}
    if isinstance(template, list):
        return [_resolve_template(v, context) for v in template]
    return template


class WebhookPipelineEngine:
    def __init__(self) -> None:
        self._pipelines: dict[str, WebhookPipeline] = {}
        self._runs: dict[str, deque[PipelineRun]] = {}
        self._all_runs: dict[str, PipelineRun] = {}
        self._lock = Lock()

    def register(self, pipeline: WebhookPipeline) -> WebhookPipeline:
        if not pipeline.name:
            raise DataConnectionWebhookError("MISSING_NAME", "name is required")
        if not pipeline.steps:
            raise DataConnectionWebhookError("EMPTY_STEPS", "steps cannot be empty")
        step_ids = [s.step_id for s in pipeline.steps if s.step_id]
        if len(step_ids) != len(set(step_ids)):
            raise DataConnectionWebhookError(
                "DUPLICATE_STEP_ID", "duplicate step_id found"
            )
        for step in pipeline.steps:
            if step.method and step.method.upper() not in _VALID_HTTP_METHODS:
                raise DataConnectionWebhookError(
                    "INVALID_METHOD", f"method must be one of {_VALID_HTTP_METHODS}"
                )
            if step.auth_type not in _VALID_WEBHOOK_AUTH_TYPES:
                raise DataConnectionWebhookError(
                    "INVALID_AUTH_TYPE",
                    f"auth_type must be one of {_VALID_WEBHOOK_AUTH_TYPES}",
                )
            if step.timeout_ms <= 0:
                raise DataConnectionWebhookError(
                    "INVALID_TIMEOUT", "timeout_ms must be > 0"
                )
        with self._lock:
            pipeline.id = f"wpl-{uuid.uuid4().hex[:8]}"
            pipeline.created_at = time.time()
            for i, step in enumerate(pipeline.steps):
                if not step.step_id:
                    step.step_id = f"step-{i+1}"
            self._pipelines[pipeline.id] = pipeline
            self._runs[pipeline.id] = deque(maxlen=_MAX_RUNS_PER_PIPELINE)
            if len(self._pipelines) > _MAX_PIPELINES:
                oldest = min(self._pipelines.values(), key=lambda p: p.created_at)
                for run in self._runs.get(oldest.id, []):
                    self._all_runs.pop(run.run_id, None)
                self._pipelines.pop(oldest.id, None)
                self._runs.pop(oldest.id, None)
            return pipeline.model_copy(deep=True)

    def get(self, pipeline_id: str) -> WebhookPipeline:
        with self._lock:
            p = self._pipelines.get(pipeline_id)
            if not p:
                raise DataConnectionWebhookError(
                    "NOT_FOUND", f"pipeline {pipeline_id} not found"
                )
            return p.model_copy(deep=True)

    def list(
        self,
        name: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[WebhookPipeline]:
        with self._lock:
            result = list(self._pipelines.values())
            if name:
                result = [p for p in result if name in p.name]
            if status:
                result = [p for p in result if p.status == status]
            return [p.model_copy(deep=True) for p in result]

    def update(self, pipeline_id: str, updates: dict) -> WebhookPipeline:
        with self._lock:
            p = self._pipelines.get(pipeline_id)
            if not p:
                raise DataConnectionWebhookError(
                    "NOT_FOUND", f"pipeline {pipeline_id} not found"
                )
            data = p.model_dump()
            data.update({k: v for k, v in updates.items() if k in {
                "name", "description", "status",
            }})
            if not data["name"]:
                raise DataConnectionWebhookError("MISSING_NAME", "name is required")
            updated = WebhookPipeline(**data)
            self._pipelines[pipeline_id] = updated
            return updated.model_copy(deep=True)

    def delete(self, pipeline_id: str) -> bool:
        with self._lock:
            if pipeline_id in self._pipelines:
                for run in self._runs.get(pipeline_id, []):
                    self._all_runs.pop(run.run_id, None)
                del self._pipelines[pipeline_id]
                self._runs.pop(pipeline_id, None)
                return True
            return False

    def add_step(
        self,
        pipeline_id: str,
        step: WebhookPipelineStep,
    ) -> WebhookPipeline:
        with self._lock:
            p = self._pipelines.get(pipeline_id)
            if not p:
                raise DataConnectionWebhookError(
                    "NOT_FOUND", f"pipeline {pipeline_id} not found"
                )
            if not step.step_id:
                step.step_id = f"step-{len(p.steps) + 1}"
            if any(s.step_id == step.step_id for s in p.steps):
                raise DataConnectionWebhookError(
                    "DUPLICATE_STEP_ID", f"step_id {step.step_id} already exists"
                )
            if step.method and step.method.upper() not in _VALID_HTTP_METHODS:
                raise DataConnectionWebhookError(
                    "INVALID_METHOD", f"method must be one of {_VALID_HTTP_METHODS}"
                )
            if step.auth_type not in _VALID_WEBHOOK_AUTH_TYPES:
                raise DataConnectionWebhookError(
                    "INVALID_AUTH_TYPE",
                    f"auth_type must be one of {_VALID_WEBHOOK_AUTH_TYPES}",
                )
            p.steps.append(step)
            return p.model_copy(deep=True)

    def remove_step(self, pipeline_id: str, step_id: str) -> WebhookPipeline:
        with self._lock:
            p = self._pipelines.get(pipeline_id)
            if not p:
                raise DataConnectionWebhookError(
                    "NOT_FOUND", f"pipeline {pipeline_id} not found"
                )
            if not any(s.step_id == step_id for s in p.steps):
                raise DataConnectionWebhookError(
                    "STEP_NOT_FOUND", f"step {step_id} not found"
                )
            p.steps = [s for s in p.steps if s.step_id != step_id]
            return p.model_copy(deep=True)

    def reorder_steps(
        self,
        pipeline_id: str,
        step_order: list[str],
    ) -> WebhookPipeline:
        with self._lock:
            p = self._pipelines.get(pipeline_id)
            if not p:
                raise DataConnectionWebhookError(
                    "NOT_FOUND", f"pipeline {pipeline_id} not found"
                )
            existing_ids = {s.step_id for s in p.steps}
            if set(step_order) != existing_ids:
                raise DataConnectionWebhookError(
                    "INVALID_ORDER", "step_order must contain all step IDs exactly once"
                )
            step_map = {s.step_id: s for s in p.steps}
            p.steps = [step_map[sid] for sid in step_order]
            return p.model_copy(deep=True)

    def run(self, pipeline_id: str, initial_input: dict) -> PipelineRun:
        with self._lock:
            p = self._pipelines.get(pipeline_id)
            if not p:
                raise DataConnectionWebhookError(
                    "NOT_FOUND", f"pipeline {pipeline_id} not found"
                )
            if p.status == "disabled":
                raise DataConnectionWebhookError(
                    "PIPELINE_DISABLED", "pipeline is disabled"
                )
            run = PipelineRun(
                run_id=f"prn-{uuid.uuid4().hex[:8]}",
                pipeline_id=pipeline_id,
                status="running",
                started_at=time.time(),
                initial_input=initial_input,
            )
            context = {"input": initial_input, "outputs": {}}
            step_results = []
            for i, step in enumerate(p.steps):
                run.current_step = i
                resolved_body = _resolve_template(step.request_template, context)
                step_result = {
                    "step_id": step.step_id,
                    "name": step.name,
                    "status": "completed",
                    "request": resolved_body,
                    "response": {
                        "status_code": 200,
                        "data": {"id": f"result-{step.step_id}", "value": f"output-{i}"},
                    },
                }
                for out_name, resp_path in step.output_mapping.items():
                    keys = resp_path.split(".")
                    val: object = step_result["response"]
                    for k in keys:
                        if isinstance(val, dict) and k in val:
                            val = val[k]
                        else:
                            val = None
                            break
                    context["outputs"][out_name] = val
                step_results.append(step_result)
            run.status = "completed"
            run.completed_at = time.time()
            run.step_results = step_results
            run.outputs = dict(context["outputs"])
            self._runs[pipeline_id].append(run)
            self._all_runs[run.run_id] = run
            p.total_runs += 1
            return run.model_copy(deep=True)

    def list_runs(
        self,
        pipeline_id: str,
        limit: int = 20,
    ) -> list[PipelineRun]:
        with self._lock:
            if pipeline_id not in self._pipelines:
                raise DataConnectionWebhookError(
                    "NOT_FOUND", f"pipeline {pipeline_id} not found"
                )
            runs = list(self._runs.get(pipeline_id, []))
            runs.sort(key=lambda r: r.started_at, reverse=True)
            return [r.model_copy(deep=True) for r in runs[:limit]]

    def get_run(self, run_id: str) -> PipelineRun:
        with self._lock:
            r = self._all_runs.get(run_id)
            if not r:
                raise DataConnectionWebhookError(
                    "RUN_NOT_FOUND", f"run {run_id} not found"
                )
            return r.model_copy(deep=True)


_webhook_pipeline_engine: Optional[WebhookPipelineEngine] = None
_webhook_pipeline_lock = Lock()


def get_webhook_pipeline_engine() -> WebhookPipelineEngine:
    global _webhook_pipeline_engine
    if _webhook_pipeline_engine is None:
        with _webhook_pipeline_lock:
            if _webhook_pipeline_engine is None:
                _webhook_pipeline_engine = WebhookPipelineEngine()
    return _webhook_pipeline_engine


# ════════════════════ #124 Webhook Output ════════════════════

class OutputFieldMapping(BaseModel):
    field_id: str = ""
    source_path: str = ""
    target_name: str = ""
    target_type: str = "string"
    required: bool = False
    default_value: object = None


class WebhookOutputConfig(BaseModel):
    id: str = ""
    name: str
    description: str = ""
    webhook_id: str = ""
    output_fields: list[OutputFieldMapping] = Field(default_factory=list)
    response_code_field: str = ""
    success_codes: list[str] = Field(default_factory=list)
    error_message_field: str = ""
    created_at: float = 0.0


class OutputExtractionResult(BaseModel):
    success: bool = True
    fields: dict = Field(default_factory=dict)
    missing_required: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    raw_response: dict = Field(default_factory=dict)


def _get_by_path(data: dict, path: str) -> object:
    keys = path.split(".")
    val: object = data
    for k in keys:
        if isinstance(val, dict) and k in val:
            val = val[k]
        else:
            return None
    return val


def _convert_type(value: object, target_type: str) -> tuple[object, Optional[str]]:
    if value is None:
        return None, None
    try:
        if target_type == "string":
            return str(value), None
        if target_type == "integer":
            return int(value), None
        if target_type == "float":
            return float(value), None
        if target_type == "boolean":
            if isinstance(value, bool):
                return value, None
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes"), None
            return bool(value), None
        if target_type == "json":
            return value, None
    except (ValueError, TypeError) as e:
        return None, str(e)
    return value, None


class WebhookOutputEngine:
    def __init__(self) -> None:
        self._configs: dict[str, WebhookOutputConfig] = {}
        self._lock = Lock()

    def register(self, config: WebhookOutputConfig) -> WebhookOutputConfig:
        if not config.name:
            raise DataConnectionWebhookError("MISSING_NAME", "name is required")
        if not config.webhook_id:
            raise DataConnectionWebhookError("MISSING_WEBHOOK", "webhook_id is required")
        field_ids = [f.field_id for f in config.output_fields if f.field_id]
        if len(field_ids) != len(set(field_ids)):
            raise DataConnectionWebhookError(
                "DUPLICATE_FIELD_ID", "duplicate field_id found"
            )
        for field in config.output_fields:
            if field.target_type not in _VALID_TARGET_TYPES:
                raise DataConnectionWebhookError(
                    "INVALID_TARGET_TYPE",
                    f"target_type must be one of {_VALID_TARGET_TYPES}",
                )
            if not field.source_path:
                raise DataConnectionWebhookError(
                    "INVALID_SOURCE_PATH", "source_path is required"
                )
        with self._lock:
            config.id = f"woc-{uuid.uuid4().hex[:8]}"
            config.created_at = time.time()
            for i, field in enumerate(config.output_fields):
                if not field.field_id:
                    field.field_id = f"fld-{i+1}"
            self._configs[config.id] = config
            if len(self._configs) > _MAX_OUTPUT_CONFIGS:
                oldest = min(self._configs.values(), key=lambda c: c.created_at)
                self._configs.pop(oldest.id, None)
            return config.model_copy(deep=True)

    def get(self, config_id: str) -> WebhookOutputConfig:
        with self._lock:
            c = self._configs.get(config_id)
            if not c:
                raise DataConnectionWebhookError(
                    "NOT_FOUND", f"config {config_id} not found"
                )
            return c.model_copy(deep=True)

    def list(
        self,
        webhook_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> list[WebhookOutputConfig]:
        with self._lock:
            result = list(self._configs.values())
            if webhook_id:
                result = [c for c in result if c.webhook_id == webhook_id]
            if name:
                result = [c for c in result if name in c.name]
            return [c.model_copy(deep=True) for c in result]

    def update(self, config_id: str, updates: dict) -> WebhookOutputConfig:
        with self._lock:
            c = self._configs.get(config_id)
            if not c:
                raise DataConnectionWebhookError(
                    "NOT_FOUND", f"config {config_id} not found"
                )
            data = c.model_dump()
            data.update({k: v for k, v in updates.items() if k in {
                "name", "description", "response_code_field",
                "success_codes", "error_message_field",
            }})
            if not data["name"]:
                raise DataConnectionWebhookError("MISSING_NAME", "name is required")
            updated = WebhookOutputConfig(**data)
            self._configs[config_id] = updated
            return updated.model_copy(deep=True)

    def delete(self, config_id: str) -> bool:
        with self._lock:
            if config_id in self._configs:
                del self._configs[config_id]
                return True
            return False

    def add_field(
        self,
        config_id: str,
        field: OutputFieldMapping,
    ) -> WebhookOutputConfig:
        with self._lock:
            c = self._configs.get(config_id)
            if not c:
                raise DataConnectionWebhookError(
                    "NOT_FOUND", f"config {config_id} not found"
                )
            if not field.field_id:
                field.field_id = f"fld-{len(c.output_fields) + 1}"
            if any(f.field_id == field.field_id for f in c.output_fields):
                raise DataConnectionWebhookError(
                    "DUPLICATE_FIELD_ID", f"field_id {field.field_id} already exists"
                )
            if field.target_type not in _VALID_TARGET_TYPES:
                raise DataConnectionWebhookError(
                    "INVALID_TARGET_TYPE",
                    f"target_type must be one of {_VALID_TARGET_TYPES}",
                )
            if not field.source_path:
                raise DataConnectionWebhookError(
                    "INVALID_SOURCE_PATH", "source_path is required"
                )
            c.output_fields.append(field)
            return c.model_copy(deep=True)

    def remove_field(self, config_id: str, field_id: str) -> WebhookOutputConfig:
        with self._lock:
            c = self._configs.get(config_id)
            if not c:
                raise DataConnectionWebhookError(
                    "NOT_FOUND", f"config {config_id} not found"
                )
            if not any(f.field_id == field_id for f in c.output_fields):
                raise DataConnectionWebhookError(
                    "FIELD_NOT_FOUND", f"field {field_id} not found"
                )
            c.output_fields = [f for f in c.output_fields if f.field_id != field_id]
            return c.model_copy(deep=True)

    def extract(
        self,
        config_id: str,
        response: dict,
    ) -> OutputExtractionResult:
        c = self.get(config_id)
        result = OutputExtractionResult(raw_response=response)
        fields: dict[str, object] = {}
        missing: list[str] = []
        errors: list[str] = []
        for field in c.output_fields:
            raw_val = _get_by_path(response, field.source_path)
            if raw_val is None:
                if field.required:
                    if field.default_value is not None:
                        converted, err = _convert_type(field.default_value, field.target_type)
                        if err:
                            errors.append(f"field {field.target_name}: default value convert error: {err}")
                            missing.append(field.target_name)
                        else:
                            fields[field.target_name] = converted
                    else:
                        missing.append(field.target_name)
                continue
            converted, err = _convert_type(raw_val, field.target_type)
            if err:
                errors.append(f"field {field.target_name}: {err}")
                if field.required:
                    missing.append(field.target_name)
                continue
            fields[field.target_name] = converted
        result.fields = fields
        result.missing_required = missing
        result.errors = errors
        result.success = len(missing) == 0 and len(errors) == 0
        return result

    def validate_response(self, config_id: str, response: dict) -> dict:
        c = self.get(config_id)
        if not c.response_code_field:
            return {"valid": True, "code": None, "message": ""}
        code_val = _get_by_path(response, c.response_code_field)
        code_str = str(code_val) if code_val is not None else ""
        is_success = True
        message = ""
        if c.success_codes:
            is_success = code_str in c.success_codes
            if not is_success and c.error_message_field:
                msg_val = _get_by_path(response, c.error_message_field)
                message = str(msg_val) if msg_val is not None else ""
        return {
            "valid": is_success,
            "code": code_str,
            "message": message,
        }


_webhook_output_engine: Optional[WebhookOutputEngine] = None
_webhook_output_lock = Lock()


def get_webhook_output_engine() -> WebhookOutputEngine:
    global _webhook_output_engine
    if _webhook_output_engine is None:
        with _webhook_output_lock:
            if _webhook_output_engine is None:
                _webhook_output_engine = WebhookOutputEngine()
    return _webhook_output_engine
