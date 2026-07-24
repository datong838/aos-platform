"""W2-6 · Pipeline Builder 输出系统（6 种写入模式）。

APPEND / SNAPSHOT / UPSERT / REPLACE / UPDATE / DELETE 六种写入语义，
复用 W1-6 WritebackLayer 的 L1 overlay 模式。

详见 docs/palantier/20_tech/220tech_w2-wave-plan.md 第一批。
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

WriteMode = Literal["append", "snapshot", "upsert", "replace", "update", "delete"]


class OutputConfig(BaseModel):
    target_dataset_rid: str
    write_mode: WriteMode = "append"
    primary_key: str = ""


class OutputTarget(BaseModel):
    id: str = Field(default_factory=lambda: "out-" + uuid.uuid4().hex[:10])
    config: OutputConfig
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class OutputResult(BaseModel):
    target_id: str
    write_mode: WriteMode
    rows_written: int
    rows_before: int
    rows_after: int
    snapshot_version: str | None = None


class PipelineOutputError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class PipelineOutputEngine:
    def __init__(self) -> None:
        self._targets: dict[str, OutputTarget] = {}
        self._datasets: dict[str, list[dict[str, Any]]] = {}
        self._snapshots: dict[str, list[str]] = {}

    def register_target(self, target: OutputTarget) -> OutputTarget:
        self._targets[target.id] = target
        return target

    def get_target(self, target_id: str) -> OutputTarget | None:
        return self._targets.get(target_id)

    def list_targets(self) -> list[OutputTarget]:
        return list(self._targets.values())

    def seed_dataset(self, rid: str, rows: list[dict[str, Any]]) -> None:
        self._datasets[rid] = [copy.deepcopy(r) for r in rows]

    def get_dataset(self, rid: str) -> list[dict[str, Any]]:
        return list(self._datasets.get(rid, []))

    def execute(self, target_id: str, input_rows: list[dict[str, Any]]) -> OutputResult:
        target = self._targets.get(target_id)
        if target is None:
            raise PipelineOutputError("NOT_FOUND", f"输出目标 {target_id} 不存在")
        cfg = target.config
        rid = cfg.target_dataset_rid
        existing = self._datasets.get(rid, [])
        rows_before = len(existing)

        if cfg.write_mode == "append":
            new_rows = existing + copy.deepcopy(input_rows)
        elif cfg.write_mode == "snapshot":
            ver = f"v{len(self._snapshots.get(rid, [])) + 1}-{uuid.uuid4().hex[:6]}"
            self._snapshots.setdefault(rid, []).append(ver)
            new_rows = copy.deepcopy(input_rows)
            return OutputResult(
                target_id=target_id, write_mode="snapshot",
                rows_written=len(input_rows), rows_before=rows_before,
                rows_after=len(new_rows), snapshot_version=ver,
            )
        elif cfg.write_mode == "replace":
            new_rows = copy.deepcopy(input_rows)
        elif cfg.write_mode == "upsert":
            pk = cfg.primary_key
            if not pk:
                raise PipelineOutputError("PK_REQUIRED", "upsert 模式需要 primary_key")
            index = {r.get(pk): r for r in existing}
            for row in input_rows:
                index[row.get(pk)] = copy.deepcopy(row)
            new_rows = list(index.values())
        elif cfg.write_mode == "update":
            pk = cfg.primary_key
            if not pk:
                raise PipelineOutputError("PK_REQUIRED", "update 模式需要 primary_key")
            index = {r.get(pk): r for r in existing}
            updated = 0
            for row in input_rows:
                key = row.get(pk)
                if key in index:
                    merged = {**index[key], **copy.deepcopy(row)}
                    index[key] = merged
                    updated += 1
            new_rows = list(index.values())
            self._datasets[rid] = new_rows
            return OutputResult(
                target_id=target_id, write_mode="update",
                rows_written=updated, rows_before=rows_before,
                rows_after=len(new_rows),
            )
        elif cfg.write_mode == "delete":
            pk = cfg.primary_key
            if not pk:
                raise PipelineOutputError("PK_REQUIRED", "delete 模式需要 primary_key")
            keys_to_delete = {row.get(pk) for row in input_rows}
            deleted = sum(1 for r in existing if r.get(pk) in keys_to_delete)
            new_rows = [r for r in existing if r.get(pk) not in keys_to_delete]
            self._datasets[rid] = new_rows
            return OutputResult(
                target_id=target_id, write_mode="delete",
                rows_written=deleted, rows_before=rows_before,
                rows_after=len(new_rows),
            )
        else:
            raise PipelineOutputError("UNKNOWN_MODE", f"未知写入模式：{cfg.write_mode}")

        self._datasets[rid] = new_rows
        return OutputResult(
            target_id=target_id, write_mode=cfg.write_mode,
            rows_written=len(input_rows), rows_before=rows_before,
            rows_after=len(new_rows),
        )


_engine = PipelineOutputEngine()


def get_engine() -> PipelineOutputEngine:
    return _engine
