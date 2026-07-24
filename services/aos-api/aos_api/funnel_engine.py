"""W1-5 · Funnel 四阶段管道引擎。

Changelog → Merge → Indexing → Hydration 四阶段顺序执行，
每阶段有独立的输入/输出/状态/日志。

详见 docs/palantier/20_tech/220tech_funnel-pipeline.md。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


STAGE_ORDER = ["changelog", "merge", "indexing", "hydration"]

PipelineMode = Literal["snapshot", "incremental"]
_VALID_OPS = {"UPSERT", "UPDATE", "DELETE"}


class StageResult(BaseModel):
    name: str
    status: str = "PENDING"
    input_count: int = 0
    output_count: int = 0
    started_at: str | None = None
    finished_at: str | None = None
    logs: list[str] = Field(default_factory=list)
    op_counts: dict[str, int] = Field(default_factory=dict)


class FunnelPipeline(BaseModel):
    id: str
    source_dataset: str
    target_object_type: str
    primary_key: str
    status: str = "PENDING"
    stages: list[StageResult] = Field(default_factory=list)
    created_at: str
    finished_at: str | None = None
    error: str | None = None
    mode: PipelineMode = "snapshot"
    watermark: str | None = None


class FunnelError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class FunnelEngine:
    def __init__(self) -> None:
        self._pipelines: dict[str, FunnelPipeline] = {}

    def run(
        self,
        source_dataset: str,
        target_object_type: str,
        primary_key: str,
        input_rows: list[dict[str, Any]] | None = None,
        mode: PipelineMode = "snapshot",
    ) -> FunnelPipeline:
        if not source_dataset:
            raise FunnelError("INVALID_INPUT", "source_dataset 不可为空")
        if not primary_key:
            raise FunnelError("INVALID_INPUT", "primary_key 不可为空")
        rows = input_rows or []
        pipeline = FunnelPipeline(
            id=str(uuid.uuid4()),
            source_dataset=source_dataset,
            target_object_type=target_object_type,
            primary_key=primary_key,
            stages=[StageResult(name=s) for s in STAGE_ORDER],
            created_at=_now(),
            mode=mode,
        )
        self._pipelines[pipeline.id] = pipeline
        try:
            data = rows
            data = self._run_changelog(pipeline, data)
            data = self._run_merge(pipeline, data, primary_key)
            data = self._run_indexing(pipeline, data, primary_key)
            data = self._run_hydration(pipeline, data, target_object_type)
            pipeline.status = "SUCCEEDED"
            pipeline.finished_at = _now()
            if mode == "incremental":
                pipeline.watermark = _now()
        except FunnelError as exc:
            pipeline.status = "FAILED"
            pipeline.error = exc.message
            pipeline.finished_at = _now()
        return pipeline

    def reindex(
        self,
        source_dataset: str,
        target_object_type: str,
        primary_key: str,
        input_rows: list[dict[str, Any]] | None = None,
    ) -> FunnelPipeline:
        """全量重索引触发：以 snapshot 模式重跑，并重置增量水位。"""
        existing = [
            p for p in self._pipelines.values()
            if p.source_dataset == source_dataset and p.target_object_type == target_object_type
        ]
        for p in existing:
            p.watermark = None
        return self.run(
            source_dataset=source_dataset,
            target_object_type=target_object_type,
            primary_key=primary_key,
            input_rows=input_rows,
            mode="snapshot",
        )

    def _run_stage(
        self, pipeline: FunnelPipeline, stage_name: str, input_data: list[dict]
    ) -> list[dict]:
        stage = next(s for s in pipeline.stages if s.name == stage_name)
        stage.status = "RUNNING"
        stage.started_at = _now()
        stage.input_count = len(input_data)
        stage.logs.append(f"{stage_name} 开始处理 {len(input_data)} 条记录")
        return input_data

    def _finish_stage(
        self, pipeline: FunnelPipeline, stage_name: str, output_data: list[dict]
    ) -> list[dict]:
        stage = next(s for s in pipeline.stages if s.name == stage_name)
        stage.output_count = len(output_data)
        stage.status = "SUCCEEDED"
        stage.finished_at = _now()
        stage.logs.append(f"{stage_name} 完成，输出 {len(output_data)} 条")
        return output_data

    def _run_changelog(
        self, pipeline: FunnelPipeline, rows: list[dict]
    ) -> list[dict]:
        self._run_stage(pipeline, "changelog", rows)
        changes: list[dict] = []
        op_counts: dict[str, int] = {}
        for r in rows:
            raw_op = r.get("_op") or r.get("_change_type") or r.get("_changeType") or "UPSERT"
            op = str(raw_op).strip().upper()
            if op not in _VALID_OPS:
                op = "UPSERT"
            op_counts[op] = op_counts.get(op, 0) + 1
            changes.append({**r, "_op": op})
        stage = next(s for s in pipeline.stages if s.name == "changelog")
        stage.op_counts = op_counts
        self._finish_stage(pipeline, "changelog", changes)
        return changes

    def _run_merge(
        self, pipeline: FunnelPipeline, rows: list[dict], pk: str
    ) -> list[dict]:
        self._run_stage(pipeline, "merge", rows)
        merged: dict[Any, dict] = {}
        deleted = 0
        for r in rows:
            if str(r.get("_op", "UPSERT")).upper() == "DELETE":
                key = r.get(pk)
                if key is not None and key in merged:
                    del merged[key]
                deleted += 1
                continue
            key = r.get(pk)
            if key is not None:
                merged[key] = r
        result = list(merged.values())
        if deleted:
            stage = next(s for s in pipeline.stages if s.name == "merge")
            stage.logs.append(f"merge 剔除 {deleted} 条 DELETE 变更")
        self._finish_stage(pipeline, "merge", result)
        return result

    def _run_indexing(
        self, pipeline: FunnelPipeline, rows: list[dict], pk: str
    ) -> list[dict]:
        self._run_stage(pipeline, "indexing", rows)
        indexed = sorted(rows, key=lambda r: str(r.get(pk, "")))
        self._finish_stage(pipeline, "indexing", indexed)
        return indexed

    def _run_hydration(
        self, pipeline: FunnelPipeline, rows: list[dict], object_type: str
    ) -> list[dict]:
        self._run_stage(pipeline, "hydration", rows)
        hydrated = [{**r, "_object_type": object_type} for r in rows]
        self._finish_stage(pipeline, "hydration", hydrated)
        return hydrated

    def get_pipeline(self, pipeline_id: str) -> FunnelPipeline | None:
        return self._pipelines.get(pipeline_id)

    def list_pipelines(self) -> list[FunnelPipeline]:
        return list(self._pipelines.values())

    def get_stage(self, pipeline_id: str, stage_name: str) -> StageResult:
        p = self._pipelines.get(pipeline_id)
        if p is None:
            raise FunnelError("NOT_FOUND", f"Pipeline {pipeline_id} 不存在")
        if stage_name not in STAGE_ORDER:
            raise FunnelError("INVALID_STAGE", f"未知阶段 {stage_name}")
        return next(s for s in p.stages if s.name == stage_name)


_engine = FunnelEngine()


def get_engine() -> FunnelEngine:
    return _engine
